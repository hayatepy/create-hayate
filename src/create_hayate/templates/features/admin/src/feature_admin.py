"""Fail-closed operational admin for the generated checked-SQL TODO resource."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import cast
from uuid import uuid4

from hayate import Context, Hayate
from hayate_sql import Database
from hayate_sql.adapters import SQLiteDatabase

import queries
from hayate_admin import (
    Actor,
    AdminAction,
    AdminField,
    AdminResource,
    AdminSite,
    AdminValidationError,
    AuditEvent,
    AuditHistoryPage,
    AuditPhase,
    ListQuery,
    Page,
    Record,
)
from identity import principal, subject
from storage import database

# Replace this set with the exact origins that serve /admin. AdminSite rejects
# mutation requests unless Origin matches one of these values exactly.
ADMIN_ALLOWED_ORIGINS = frozenset(
    {
        "http://localhost",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8787",
        "https://app.example.com",
    }
)


def _record(row: Mapping[str, object]) -> Record:
    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
    }


def _title(values: Mapping[str, object]) -> str:
    value = values.get("title")
    if not isinstance(value, str):
        raise AdminValidationError({"title": "A title is required."})
    normalized = value.strip()
    if not normalized:
        raise AdminValidationError({"title": "A title is required."})
    return normalized


def _done(values: Mapping[str, object]) -> bool:
    value = values.get("done")
    if not isinstance(value, bool):
        raise AdminValidationError({"done": "A checkbox value is required."})
    return value


class TodoAdminRepository:
    """One identity-scoped repository backed only by generated SQL calls."""

    def __init__(self, db: Database, owner: str) -> None:
        self._db = db
        self._owner = owner

    async def _list_page(self, query: ListQuery) -> Page:
        search = query.search or ""
        count = await queries.count_admin_todos(
            self._db,
            owner=self._owner,
            search=search,
        )
        if query.order_by is None:
            list_query = queries.list_admin_todos_default
        elif query.order_by == "title" and query.descending:
            list_query = queries.list_admin_todos_title_desc
        elif query.order_by == "title":
            list_query = queries.list_admin_todos_title_asc
        else:
            raise ValueError("unsupported admin TODO order")
        rows = await list_query(
            self._db,
            owner=self._owner,
            search=search,
            limit=query.limit,
            offset=query.offset,
        )
        return Page(tuple(_record(row) for row in rows), int(count["total"]))

    async def list(self, query: ListQuery) -> Page:
        if query.filters:
            raise ValueError("the TODO admin does not define filters")
        if isinstance(self._db, SQLiteDatabase):
            async with self._db.transaction():
                return await self._list_page(query)
        return await self._list_page(query)

    async def get(self, object_id: str) -> Record | None:
        row = await queries.get_todo(
            self._db,
            owner=self._owner,
            todo_id=object_id,
        )
        return None if row is None else _record(row)

    async def create(self, values: Mapping[str, object]) -> Record:
        row = await queries.create_admin_todo(
            self._db,
            todo_id=str(uuid4()),
            owner=self._owner,
            title=_title(values),
            done=_done(values),
        )
        return _record(row)

    async def update(
        self,
        object_id: str,
        values: Mapping[str, object],
    ) -> Record | None:
        row = await queries.update_admin_todo(
            self._db,
            owner=self._owner,
            todo_id=object_id,
            title=_title(values),
            done=_done(values),
        )
        return None if row is None else _record(row)

    async def delete(self, object_id: str) -> bool:
        result = await queries.delete_todo(
            self._db,
            owner=self._owner,
            todo_id=object_id,
        )
        return result.rows_affected == 1


def _repository(context: Context) -> TodoAdminRepository:
    return TodoAdminRepository(database(context), subject(context))


def _operator_emails(context: Context) -> frozenset[str]:
    raw = getattr(context.env, "ADMIN_EMAILS", None) if context.env is not None else None
    if not isinstance(raw, str) or not raw or len(raw) > 4096:
        return frozenset()
    emails = tuple(value.strip().casefold() for value in raw.split(",") if value.strip())
    if len(emails) > 100 or any("@" not in email for email in emails):
        return frozenset()
    return frozenset(emails)


async def _authorize(
    context: Context,
    action: AdminAction,
    resource: AdminResource | None,
    object_id: str | None,
) -> Actor | None:
    del action, resource, object_id
    identity = principal(context)
    email = identity["email"]
    if email is None or email.casefold() not in _operator_emails(context):
        return None
    return Actor(id=identity["subject"], display=email)


def _audit_factory(context: Context):
    db = database(context)
    owner = subject(context)

    async def audit(event: AuditEvent) -> None:
        await queries.create_admin_audit_event(
            db,
            owner=owner,
            occurred_at=event.occurred_at.isoformat(),
            phase=event.phase,
            action=event.action,
            operation=event.operation,
            resource=event.resource or "site",
            object_id=event.object_id,
            actor_id=event.actor_id,
            error_type=event.error_type,
        )

    return audit


def _history_factory(context: Context):
    db = database(context)
    owner = subject(context)

    async def history(
        _context: Context,
        resource: AdminResource,
        object_id: str,
        offset: int,
        limit: int,
    ) -> AuditHistoryPage:
        count = await queries.count_admin_audit_events(
            db,
            owner=owner,
            resource=resource.slug,
            object_id=object_id,
        )
        rows = await queries.list_admin_audit_events(
            db,
            owner=owner,
            resource=resource.slug,
            object_id=object_id,
            limit=limit,
            offset=offset,
        )
        events = tuple(
            AuditEvent(
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
                phase=cast(AuditPhase, row["phase"]),
                action=cast(AdminAction, row["action"]),
                operation=row["operation"],
                resource=row["resource"],
                object_id=row["object_id"],
                actor_id=row["actor_id"],
                error_type=row["error_type"],
            )
            for row in rows
        )
        return AuditHistoryPage(events, int(count["total"]))

    return history


def register(app: Hayate) -> None:
    """Register one explicit resource; add application resources here."""
    site = AdminSite(
        title="$project_name Operations",
        allowed_origins=set(ADMIN_ALLOWED_ORIGINS),
        authorize=_authorize,
        audit_factory=_audit_factory,
        history_factory=_history_factory,
    )
    site.add(
        AdminResource(
            slug="todos",
            label="TODOs",
            singular_label="TODO",
            repository=_repository,
            title_field="title",
            fields=(
                AdminField(
                    "id",
                    "ID",
                    required=False,
                    read_only=True,
                ),
                AdminField(
                    "title",
                    "Title",
                    searchable=True,
                    sortable=True,
                    max_length=200,
                ),
                AdminField("done", "Done", kind="checkbox"),
            ),
        )
    )
    site.register(app)
