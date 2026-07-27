"""Fail-closed admin route registration and operation orchestration."""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from types import MappingProxyType
from urllib.parse import quote, urlsplit

from hayate import (
    Context,
    File,
    FormDataLimitError,
    FormDataLimits,
    Hayate,
    Response,
    problem,
)
from hayate_htmx import HtmxRequest, with_htmx

from .contracts import (
    Actor,
    AdminAction,
    AdminAsset,
    AdminBulkAction,
    AdminCsvExport,
    AdminCursorError,
    AdminInline,
    AdminRelationship,
    AdminResource,
    AdminValidationError,
    AuditEvent,
    AuditHistoryPage,
    AuditHistoryReader,
    AuditHistoryReaderFactory,
    AuditPhase,
    AuditSink,
    AuditSinkFactory,
    Authorizer,
    BulkActionResult,
    CursorPage,
    ExportQuery,
    InlineCollection,
    InlineMutation,
    InlineMutationResult,
    InlineOperation,
    ListQuery,
    Page,
    Record,
    RelationshipChoice,
    RelationshipPage,
    RelationshipQuery,
)
from .render import AdminRenderer

_FORM_BODY_LIMIT = 64 * 1024
_PREFIX = re.compile(r"^/[A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)*$")
_CURSOR = re.compile(r"^[A-Za-z0-9_-]{1,4096}$")
_REPOSITORY_CURSOR = re.compile(r"^[A-Za-z0-9._~-]{1,1536}$")


def _cursor_query_fingerprint(resource: AdminResource, query: ListQuery) -> str:
    canonical = json.dumps(
        {
            "d": query.descending,
            "f": dict(sorted(query.filters.items())),
            "o": query.order_by,
            "q": query.search,
            "r": resource.slug,
            "s": query.saved_view,
            "v": 1,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def _cursor_payload(
    resource: AdminResource,
    query: ListQuery,
    repository_cursor: str,
) -> dict[str, object]:
    return {
        "c": repository_cursor,
        "h": _cursor_query_fingerprint(resource, query),
        "r": resource.slug,
        "v": 1,
    }


def _encode_cursor(
    resource: AdminResource,
    query: ListQuery,
    repository_cursor: str,
) -> str:
    payload = json.dumps(
        _cursor_payload(resource, query, repository_cursor),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    if len(encoded) > 4096:
        raise ValueError("admin cursor envelope exceeds 4096 characters")
    return encoded


def _decode_cursor(
    raw: str,
    resource: AdminResource,
    query: ListQuery,
) -> str:
    if not _CURSOR.fullmatch(raw):
        raise ValueError("cursor must be an opaque URL-safe token")
    padding = b"=" * (-len(raw) % 4)
    try:
        decoded = base64.b64decode(
            raw.encode("ascii") + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(decoded)
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as error:
        raise ValueError("cursor is malformed") from error
    if not isinstance(payload, dict) or set(payload) != {"c", "h", "r", "v"}:
        raise ValueError("cursor has an unsupported shape")
    expected = _cursor_payload(resource, query, "")
    if any(payload[key] != expected[key] for key in expected if key != "c"):
        raise ValueError("cursor does not belong to this resource and list query")
    repository_cursor = payload["c"]
    if not isinstance(repository_cursor, str) or not _REPOSITORY_CURSOR.fullmatch(
        repository_cursor
    ):
        raise ValueError("cursor contains an invalid repository continuation")
    return repository_cursor


def _csv_cell(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    cell = str(value)
    candidate = cell.lstrip()
    if candidate.startswith(("=", "+", "-", "@")) or cell.startswith(("\t", "\r", "\n")):
        return f"'{cell}"
    return cell


def _normalize_origin(origin: str) -> str:
    if not isinstance(origin, str):
        raise ValueError(f"invalid admin allowed origin: {origin!r}")
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"invalid admin allowed origin: {origin!r}")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _normalize_prefix(prefix: str) -> str:
    if not isinstance(prefix, str):
        raise ValueError("admin prefix must be a non-root static absolute path")
    value = prefix.rstrip("/")
    if not _PREFIX.fullmatch(value):
        raise ValueError("admin prefix must be a non-root static absolute path")
    return value


class AdminSite:
    """Register an internal CRUD surface onto an ordinary Hayate application."""

    __slots__ = (
        "_audit",
        "_audit_factory",
        "_authorize",
        "_history",
        "_history_factory",
        "_registered",
        "_renderer",
        "_resources",
        "_trusted_origins",
        "prefix",
        "title",
    )

    def __init__(
        self,
        *,
        title: str,
        allowed_origins: set[str] | frozenset[str],
        authorize: Authorizer,
        audit: AuditSink | None = None,
        audit_factory: AuditSinkFactory | None = None,
        history: AuditHistoryReader | None = None,
        history_factory: AuditHistoryReaderFactory | None = None,
        prefix: str = "/admin",
        htmx_asset: AdminAsset | None = None,
    ) -> None:
        if not isinstance(title, str) or not title or len(title) > 120:
            raise ValueError("admin title must be 1-120 characters")
        if not isinstance(allowed_origins, (set, frozenset)) or not allowed_origins:
            raise ValueError("admin allowed_origins must not be empty")
        if not callable(authorize):
            raise ValueError("admin authorize must be callable")
        if (audit is None) == (audit_factory is None):
            raise ValueError("admin requires exactly one audit sink or audit_factory")
        if audit is not None and not callable(audit):
            raise ValueError("admin audit must be callable")
        if audit_factory is not None and not callable(audit_factory):
            raise ValueError("admin audit_factory must be callable")
        if history is not None and history_factory is not None:
            raise ValueError("admin accepts at most one history reader or history_factory")
        if history is not None and not callable(history):
            raise ValueError("admin history reader must be callable")
        if history_factory is not None and not callable(history_factory):
            raise ValueError("admin history_factory must be callable")
        if htmx_asset is not None and not isinstance(htmx_asset, AdminAsset):
            raise ValueError("admin htmx_asset must be an AdminAsset")
        self.title = title
        self.prefix = _normalize_prefix(prefix)
        self._trusted_origins = frozenset(_normalize_origin(origin) for origin in allowed_origins)
        self._authorize = authorize
        self._audit = audit
        self._audit_factory = audit_factory
        self._history = history
        self._history_factory = history_factory
        self._resources: dict[str, AdminResource] = {}
        self._registered = False
        self._renderer = AdminRenderer(prefix=self.prefix, title=title, asset=htmx_asset)

    @property
    def resources(self) -> tuple[AdminResource, ...]:
        return tuple(self._resources.values())

    @property
    def _has_history(self) -> bool:
        return self._history is not None or self._history_factory is not None

    def add(self, resource: AdminResource) -> AdminResource:
        """Add one resource before the site is registered."""
        if not isinstance(resource, AdminResource):
            raise ValueError("admin resource must be an AdminResource")
        if self._registered:
            raise RuntimeError("admin resources cannot be added after route registration")
        if resource.slug in self._resources:
            raise ValueError(f"duplicate admin resource slug: {resource.slug!r}")
        self._resources[resource.slug] = resource
        return resource

    def register(self, app: Hayate) -> None:
        """Register the complete route set exactly once."""
        if self._registered:
            raise RuntimeError("admin site is already registered")
        if not self._resources:
            raise RuntimeError("admin site requires at least one resource")
        self._validate_resource_graph()
        self._registered = True
        prefix = self.prefix

        @app.get(prefix)
        async def admin_index(context: Context) -> Response:
            return await self._index(context)

        @app.get(f"{prefix}/:resource")
        async def admin_list(context: Context) -> Response:
            return await self._list(context)

        @app.get(f"{prefix}/:resource/create")
        async def admin_create_form(context: Context) -> Response:
            return await self._create_form(context)

        @app.post(f"{prefix}/:resource/create")
        async def admin_create(context: Context) -> Response:
            return await self._create(context)

        @app.post(f"{prefix}/:resource/bulk")
        async def admin_bulk(context: Context) -> Response:
            return await self._bulk(context)

        @app.get(f"{prefix}/:resource/export.csv")
        async def admin_export(context: Context) -> Response:
            return await self._export_csv(context)

        @app.get(f"{prefix}/:resource/relationship/:field/choices")
        async def admin_relationship_choices(context: Context) -> Response:
            return await self._relationship_choices_view(context)

        @app.get(f"{prefix}/:resource/object/:object_id")
        async def admin_detail(context: Context) -> Response:
            return await self._detail(context)

        @app.get(f"{prefix}/:resource/object/:object_id/edit")
        async def admin_edit_form(context: Context) -> Response:
            return await self._edit_form(context)

        @app.post(f"{prefix}/:resource/object/:object_id/edit")
        async def admin_edit(context: Context) -> Response:
            return await self._edit(context)

        @app.get(f"{prefix}/:resource/object/:object_id/history")
        async def admin_history(context: Context) -> Response:
            return await self._history_view(context)

        @app.get(f"{prefix}/:resource/object/:object_id/delete")
        async def admin_delete_form(context: Context) -> Response:
            return await self._delete_form(context)

        @app.post(f"{prefix}/:resource/object/:object_id/delete")
        async def admin_delete(context: Context) -> Response:
            return await self._delete(context)

        @app.get(f"{prefix}/:resource/object/:object_id/inline/:inline")
        async def admin_inline_form(context: Context) -> Response:
            return await self._inline_form(context)

        @app.post(f"{prefix}/:resource/object/:object_id/inline/:inline")
        async def admin_inline_mutation(context: Context) -> Response:
            return await self._inline_mutation(context)

    def _validate_resource_graph(self) -> None:
        for resource in self._resources.values():
            for relationship in resource.relationships:
                if relationship.target_resource not in self._resources:
                    raise ValueError(
                        f"{resource.slug}.{relationship.field}: unknown target resource "
                        f"{relationship.target_resource!r}"
                    )
            for inline in resource.inlines:
                target = self._resources.get(inline.target_resource)
                if target is None:
                    raise ValueError(
                        f"{resource.slug}.{inline.slug}: unknown inline target "
                        f"{inline.target_resource!r}"
                    )
                parent_field = target.field_map.get(inline.parent_field)
                parent_relationship = target.relationship_map.get(inline.parent_field)
                if (
                    parent_field is None
                    or parent_field.read_only
                    or parent_relationship is None
                    or parent_relationship.target_resource != resource.slug
                ):
                    raise ValueError(
                        f"{resource.slug}.{inline.slug}: parent_field must be an explicit "
                        "relationship back to the parent resource"
                    )
                for field_name in inline.fields:
                    admin_field = target.field_map.get(field_name)
                    if (
                        admin_field is None
                        or admin_field.read_only
                        or field_name in (target.id_field, inline.parent_field)
                        or field_name in target.relationship_map
                    ):
                        raise ValueError(
                            f"{resource.slug}.{inline.slug}: inline field {field_name!r} "
                            "must be a writable non-relationship target field"
                        )

    def _resource(self, context: Context) -> AdminResource | None:
        slug = context.req.param("resource")
        return None if slug is None else self._resources.get(slug)

    @staticmethod
    def _relationship(
        context: Context,
        resource: AdminResource,
    ) -> AdminRelationship | None:
        field_name = context.req.param("field")
        return None if field_name is None else resource.relationship_map.get(field_name)

    @staticmethod
    def _inline(context: Context, resource: AdminResource) -> AdminInline | None:
        slug = context.req.param("inline")
        return None if slug is None else resource.inline_map.get(slug)

    @staticmethod
    def _object_id(context: Context) -> str | None:
        value = context.req.param("object_id")
        return value if value else None

    async def _allowed(
        self,
        context: Context,
        action: AdminAction,
        resource: AdminResource | None,
        object_id: str | None = None,
    ) -> Actor | None:
        return await self._authorize(context, action, resource, object_id)

    @staticmethod
    def _forbidden() -> Response:
        return problem(403, title="Admin operation forbidden")

    @staticmethod
    def _not_found() -> Response:
        return problem(404, title="Admin record not found")

    async def _index(self, context: Context) -> Response:
        actor = await self._allowed(context, "site:view", None)
        if actor is None:
            return self._forbidden()
        visible = []
        for resource in self._resources.values():
            if await self._allowed(context, "resource:view", resource) is not None:
                visible.append(resource)
        content = self._renderer.index(visible)
        return self._renderer.response(
            context,
            title=self.title,
            actor=actor,
            content=content,
        )

    async def _list(self, context: Context) -> Response:
        resource = self._resource(context)
        if resource is None:
            return self._not_found()
        actor = await self._allowed(context, "resource:view", resource)
        if actor is None:
            return self._forbidden()
        try:
            query = self._list_query(context, resource)
        except ValueError as error:
            return problem(400, title="Invalid admin list query", detail=str(error))
        try:
            repository_page = await resource.repository_for(context).list(query)
        except AdminCursorError:
            return problem(400, title="Admin cursor is unsupported")
        self._validate_page(resource, query, repository_page)
        visible_records = []
        for record in repository_page.items:
            visible_records.append(await self._authorized_record(context, resource, record))
        if isinstance(repository_page, CursorPage):
            next_cursor = (
                None
                if repository_page.next_cursor is None
                else _encode_cursor(resource, query, repository_page.next_cursor)
            )
            page: Page | CursorPage = CursorPage(tuple(visible_records), next_cursor)
        else:
            page = Page(tuple(visible_records), repository_page.total)
        bulk_actions: tuple[AdminBulkAction, ...] = ()
        if resource.bulk_actions and (
            await self._allowed(context, "resource:bulk", resource) is not None
        ):
            visible_actions = []
            for action in resource.bulk_actions:
                if await self._allowed(context, action.required_action, resource) is not None:
                    visible_actions.append(action)
            bulk_actions = tuple(visible_actions)
        content = self._renderer.listing(
            resource,
            page,
            query,
            can_add=await self._allowed(context, "resource:add", resource) is not None,
            can_change=await self._allowed(context, "resource:change", resource) is not None,
            can_delete=await self._allowed(context, "resource:delete", resource) is not None,
            can_export=resource.csv_export is not None
            and await self._allowed(context, "resource:export", resource) is not None,
            bulk_actions=bulk_actions,
        )
        return self._renderer.response(
            context,
            title=resource.label,
            actor=actor,
            content=content,
        )

    @staticmethod
    def _list_query(
        context: Context,
        resource: AdminResource,
        *,
        include_pagination: bool = True,
    ) -> ListQuery:
        requested_view = context.req.query("view")
        saved_view = None if requested_view is None else resource.saved_view_map.get(requested_view)
        if requested_view is not None and saved_view is None:
            raise ValueError("view must name a registered saved view")

        raw_search = context.req.query("q")
        if raw_search is None:
            search = None if saved_view is None else saved_view.search
        else:
            search = raw_search.strip() or None
        if search is not None and len(search) > 200:
            raise ValueError("search must not exceed 200 characters")

        sortable = {field.name for field in resource.fields if field.sortable}
        requested_sort = context.req.query("sort")
        if requested_sort is None:
            order_by = None if saved_view is None else saved_view.order_by
            descending = False if saved_view is None else saved_view.descending
        else:
            order_by = requested_sort if requested_sort in sortable else None
            descending = order_by is not None and context.req.query("direction") == "desc"

        filters = {}
        for admin_field in resource.fields:
            if not admin_field.filterable:
                continue
            value = context.req.query(f"filter_{admin_field.name}")
            if value is None and saved_view is not None:
                value = saved_view.filters.get(admin_field.name)
            allowed = {choice for choice, _ in admin_field.choices}
            if value in allowed:
                filters[admin_field.name] = value

        query = ListQuery(
            search=search,
            filters=filters,
            order_by=order_by,
            descending=descending,
            offset=0,
            limit=resource.page_size,
            saved_view=requested_view,
        )
        if not include_pagination:
            if context.req.query("page") is not None or context.req.query("cursor") is not None:
                raise ValueError("export queries do not accept page or cursor")
            return query

        if resource.pagination == "offset":
            if context.req.query("cursor") is not None:
                raise ValueError("this resource does not support cursor pagination")
            raw_page = context.req.query("page") or "1"
            try:
                page_number = int(raw_page)
            except ValueError as error:
                raise ValueError("page must be a positive integer") from error
            if not 1 <= page_number <= 1_000_000:
                raise ValueError("page must be in 1-1000000")
            return ListQuery(
                search=query.search,
                filters=query.filters,
                order_by=query.order_by,
                descending=query.descending,
                offset=(page_number - 1) * resource.page_size,
                limit=resource.page_size,
                saved_view=query.saved_view,
            )

        if context.req.query("page") is not None:
            raise ValueError("cursor resources do not accept page offsets")
        raw_cursor = context.req.query("cursor")
        repository_cursor = (
            None if raw_cursor is None else _decode_cursor(raw_cursor, resource, query)
        )
        return ListQuery(
            search=query.search,
            filters=query.filters,
            order_by=query.order_by,
            descending=query.descending,
            offset=0,
            limit=resource.page_size,
            cursor=repository_cursor,
            saved_view=query.saved_view,
        )

    @staticmethod
    def _validate_page(
        resource: AdminResource,
        query: ListQuery,
        page: Page | CursorPage,
    ) -> None:
        if resource.pagination == "offset" and not isinstance(page, Page):
            raise TypeError(f"{resource.slug}: offset repository must return Page")
        if resource.pagination == "cursor" and not isinstance(page, CursorPage):
            raise TypeError(f"{resource.slug}: cursor repository must return CursorPage")
        if len(page.items) > query.limit:
            raise ValueError(f"{resource.slug}: repository returned more than the requested limit")
        for record in page.items:
            AdminSite._validate_record(resource, record)

    @staticmethod
    def _validate_record(resource: AdminResource, record: Record) -> None:
        if resource.id_field not in record or record[resource.id_field] is None:
            raise ValueError(f"{resource.slug}: repository record is missing its ID")
        unknown = set(record) - set(resource.field_map)
        if unknown:
            raise ValueError(
                f"{resource.slug}: repository exposed undeclared fields: {sorted(unknown)!r}"
            )
        for relationship in resource.relationships:
            related_id = record.get(relationship.field)
            display = record.get(relationship.display_field)
            if related_id is not None and display is None:
                raise ValueError(
                    f"{resource.slug}: repository did not preload {relationship.display_field!r}"
                )

    async def _authorized_record(
        self,
        context: Context,
        resource: AdminResource,
        record: Record,
    ) -> Record:
        visible = dict(record)
        for relationship in resource.relationships:
            related_id = record.get(relationship.field)
            if related_id is None:
                continue
            target = self._resources[relationship.target_resource]
            if await self._allowed(context, "resource:view", target, str(related_id)) is None:
                visible[relationship.field] = None
                visible[relationship.display_field] = None
        return MappingProxyType(visible)

    async def _detail(self, context: Context) -> Response:
        resource = self._resource(context)
        object_id = self._object_id(context)
        if resource is None or object_id is None:
            return self._not_found()
        actor = await self._allowed(context, "resource:view", resource, object_id)
        if actor is None:
            return self._forbidden()
        record = await resource.repository_for(context).get(object_id)
        if record is None:
            return self._not_found()
        self._validate_record(resource, record)
        record = await self._authorized_record(context, resource, record)
        visible_inlines = []
        for inline in resource.inlines:
            target = self._resources[inline.target_resource]
            if await self._allowed(context, "resource:view", target) is not None:
                visible_inlines.append(inline)
        content = self._renderer.detail(
            resource,
            record,
            can_change=await self._allowed(context, "resource:change", resource, object_id)
            is not None,
            can_delete=await self._allowed(context, "resource:delete", resource, object_id)
            is not None,
            can_history=self._has_history
            and await self._allowed(context, "resource:history", resource, object_id) is not None,
            inlines=visible_inlines,
        )
        return self._renderer.response(
            context,
            title=str(record.get(resource.title_field, object_id)),
            actor=actor,
            content=content,
        )

    async def _history_view(self, context: Context) -> Response:
        resource = self._resource(context)
        object_id = self._object_id(context)
        if resource is None or object_id is None or not self._has_history:
            return self._not_found()
        actor = await self._allowed(context, "resource:history", resource, object_id)
        if actor is None:
            return self._forbidden()
        raw_page = context.req.query("page") or "1"
        try:
            page_number = int(raw_page)
        except ValueError:
            return problem(400, title="Invalid admin history page")
        if not 1 <= page_number <= 1_000_000:
            return problem(400, title="Invalid admin history page")
        limit = 50
        reader = self._history
        if reader is None:
            factory = self._history_factory
            if factory is None:
                raise RuntimeError("admin history configuration is missing")
            reader = factory(context)
        if not callable(reader):
            raise TypeError("admin history_factory returned an invalid reader")
        page = await reader(
            context,
            resource,
            object_id,
            (page_number - 1) * limit,
            limit,
        )
        self._validate_history_page(resource, object_id, page, limit)
        content = self._renderer.history(
            resource,
            object_id,
            page,
            page_number=page_number,
            limit=limit,
        )
        return self._renderer.response(
            context,
            title=f"{resource.singular_label} history",
            actor=actor,
            content=content,
        )

    async def _relationship_choices_view(self, context: Context) -> Response:
        resource = self._resource(context)
        if resource is None:
            return self._not_found()
        relationship = self._relationship(context, resource)
        if relationship is None:
            return self._not_found()
        source_object_id = context.req.query("object_id")
        if source_object_id is not None and (
            not source_object_id
            or len(source_object_id) > 255
            or any(ord(character) < 0x20 for character in source_object_id)
        ):
            return problem(400, title="Invalid relationship source object")
        source_action: AdminAction = (
            "resource:add" if source_object_id is None else "resource:change"
        )
        actor = await self._allowed(context, source_action, resource, source_object_id)
        if actor is None:
            return self._forbidden()
        if source_object_id is not None:
            source_record = await resource.repository_for(context).get(source_object_id)
            if source_record is None:
                return self._not_found()
            self._validate_record(resource, source_record)

        search = context.req.query("q")
        if search is not None:
            search = search.strip() or None
        if search is not None and len(search) > 200:
            return problem(400, title="Invalid relationship search")
        raw_page = context.req.query("page") or "1"
        try:
            page_number = int(raw_page)
        except ValueError:
            return problem(400, title="Invalid relationship page")
        if not 1 <= page_number <= 1_000_000:
            return problem(400, title="Invalid relationship page")
        query = RelationshipQuery(
            search=search,
            offset=(page_number - 1) * relationship.max_choices,
            limit=relationship.max_choices,
        )
        page = await self._search_relationship(
            context,
            resource,
            relationship,
            source_object_id,
            query,
        )
        if page is None:
            return self._forbidden()
        content = self._renderer.relationship_choices(
            resource,
            relationship,
            page,
            search=search,
            page_number=page_number,
            source_object_id=source_object_id,
        )
        return self._renderer.response(
            context,
            title=f"Choose {resource.field_map[relationship.field].label}",
            actor=actor,
            content=content,
        )

    async def _search_relationship(
        self,
        context: Context,
        resource: AdminResource,
        relationship: AdminRelationship,
        source_object_id: str | None,
        query: RelationshipQuery,
    ) -> RelationshipPage | None:
        target = self._resources[relationship.target_resource]
        if await self._allowed(context, "resource:view", target) is None:
            return None
        page = await relationship.search(
            context,
            resource,
            target,
            relationship,
            source_object_id,
            query,
        )
        if not isinstance(page, RelationshipPage):
            raise TypeError("relationship search returned an invalid page")
        if len(page.items) > query.limit:
            raise ValueError("relationship search returned more than the requested limit")
        for choice in page.items:
            if await self._allowed(context, "resource:view", target, choice.id) is None:
                raise ValueError("relationship search returned an unauthorized choice")
        return page

    async def _resolve_relationship(
        self,
        context: Context,
        resource: AdminResource,
        relationship: AdminRelationship,
        source_object_id: str | None,
        related_object_id: str,
    ) -> RelationshipChoice | None:
        target = self._resources[relationship.target_resource]
        if await self._allowed(context, "resource:view", target) is None:
            return None
        choice = await relationship.resolve(
            context,
            resource,
            target,
            relationship,
            source_object_id,
            related_object_id,
        )
        if choice is None:
            return None
        if not isinstance(choice, RelationshipChoice) or choice.id != related_object_id:
            raise ValueError("relationship resolver returned an invalid choice")
        if await self._allowed(context, "resource:view", target, choice.id) is None:
            return None
        return choice

    async def _relationship_form_state(
        self,
        context: Context,
        resource: AdminResource,
        source_object_id: str | None,
        values: Mapping[str, object],
    ) -> tuple[Mapping[str, object], Mapping[str, tuple[RelationshipChoice, ...]]] | None:
        display_values = dict(values)
        choice_pages: dict[str, tuple[RelationshipChoice, ...]] = {}
        for relationship in resource.relationships:
            page = await self._search_relationship(
                context,
                resource,
                relationship,
                source_object_id,
                RelationshipQuery(search=None, offset=0, limit=relationship.max_choices),
            )
            if page is None:
                return None
            choices = list(page.items)
            selected = context.req.query(f"relation_{relationship.field}")
            if selected is None:
                raw_selected = values.get(relationship.field)
                selected = None if raw_selected is None else str(raw_selected)
            if selected is not None:
                if (
                    not selected
                    or len(selected) > 255
                    or any(ord(character) < 0x20 for character in selected)
                ):
                    return None
                choice = await self._resolve_relationship(
                    context,
                    resource,
                    relationship,
                    source_object_id,
                    selected,
                )
                if choice is None:
                    return None
                if all(existing.id != choice.id for existing in choices):
                    choices.append(choice)
                display_values[relationship.field] = choice.id
                display_values[relationship.display_field] = choice.label
            choice_pages[relationship.field] = tuple(choices)
        return MappingProxyType(display_values), MappingProxyType(choice_pages)

    async def _create_form(self, context: Context) -> Response:
        resource = self._resource(context)
        if resource is None:
            return self._not_found()
        actor = await self._allowed(context, "resource:add", resource)
        if actor is None:
            return self._forbidden()
        relationship_state = await self._relationship_form_state(
            context,
            resource,
            None,
            {},
        )
        if relationship_state is None:
            return self._forbidden()
        values, relationship_choices = relationship_state
        content = self._renderer.form(
            resource,
            action=f"{self.prefix}/{resource.slug}/create",
            heading=f"Add {resource.singular_label}",
            values=values,
            errors={},
            submit_label="Create",
            relationship_choices=relationship_choices,
            source_object_id=None,
        )
        return self._renderer.response(
            context,
            title=f"Add {resource.singular_label}",
            actor=actor,
            content=content,
        )

    async def _create(self, context: Context) -> Response:
        resource = self._resource(context)
        if resource is None:
            return self._not_found()
        guard = await self._guard_mutation(context, "resource:add", resource, None)
        if guard is not None:
            return guard
        actor = await self._allowed(context, "resource:add", resource)
        if actor is None:
            await self._failure(
                context,
                "resource:add",
                resource,
                None,
                None,
                "AuthorizationDenied",
            )
            return self._forbidden()
        await self._event(context, "attempt", "resource:add", resource, None, actor)

        parsed = await self._parse_form(context, resource, None)
        if isinstance(parsed, Response):
            await self._failure(context, "resource:add", resource, None, actor, "InvalidForm")
            return parsed
        values, display_values, errors = parsed
        if errors:
            await self._failure(
                context,
                "resource:add",
                resource,
                None,
                actor,
                "ValidationError",
            )
            return await self._form_error_response(
                context,
                resource,
                actor=actor,
                action=f"{self.prefix}/{resource.slug}/create",
                heading=f"Add {resource.singular_label}",
                values=display_values,
                errors=errors,
                submit_label="Create",
                source_object_id=None,
            )
        try:
            record = await resource.repository_for(context).create(values)
        except AdminValidationError as error:
            await self._failure(
                context,
                "resource:add",
                resource,
                None,
                actor,
                type(error).__name__,
            )
            return await self._form_error_response(
                context,
                resource,
                actor=actor,
                action=f"{self.prefix}/{resource.slug}/create",
                heading=f"Add {resource.singular_label}",
                values=display_values,
                errors=self._safe_errors(resource, error.errors),
                submit_label="Create",
                source_object_id=None,
            )
        except Exception as error:
            await self._failure(
                context,
                "resource:add",
                resource,
                None,
                actor,
                type(error).__name__,
            )
            raise
        object_id = self._record_id(resource, record)
        self._validate_record(resource, record)
        await self._event(context, "success", "resource:add", resource, object_id, actor)
        return self._redirect(context, self._record_location(resource, object_id))

    async def _bulk(self, context: Context) -> Response:
        resource = self._resource(context)
        if resource is None:
            return self._not_found()
        guard = await self._guard_mutation(context, "resource:bulk", resource, None)
        if guard is not None:
            return guard
        actor = await self._allowed(context, "resource:bulk", resource)
        if actor is None:
            await self._failure(
                context,
                "resource:bulk",
                resource,
                None,
                None,
                "AuthorizationDenied",
            )
            return self._forbidden()
        parsed = await self._parse_bulk_form(context, resource, actor)
        if isinstance(parsed, Response):
            await self._failure(
                context,
                "resource:bulk",
                resource,
                None,
                actor,
                "InvalidBulkForm",
            )
            return parsed
        action, object_ids = parsed
        if await self._allowed(context, action.required_action, resource) is None:
            await self._failure(
                context,
                "resource:bulk",
                resource,
                None,
                actor,
                "AuthorizationDenied",
                operation=action.slug,
            )
            return self._forbidden()
        for object_id in object_ids:
            if (
                await self._allowed(
                    context,
                    action.required_action,
                    resource,
                    object_id,
                )
                is None
            ):
                await self._failure(
                    context,
                    "resource:bulk",
                    resource,
                    object_id,
                    actor,
                    "AuthorizationDenied",
                    operation=action.slug,
                )
                return self._forbidden()

        for object_id in object_ids:
            await self._event(
                context,
                "attempt",
                "resource:bulk",
                resource,
                object_id,
                actor,
                operation=action.slug,
            )
        try:
            result = await action.handler(
                context,
                resource.repository_for(context),
                object_ids,
            )
            self._validate_bulk_result(object_ids, result)
        except Exception as error:
            for object_id in object_ids:
                await self._failure(
                    context,
                    "resource:bulk",
                    resource,
                    object_id,
                    actor,
                    type(error).__name__,
                    operation=action.slug,
                )
            raise

        for object_id in result.succeeded:
            await self._event(
                context,
                "success",
                "resource:bulk",
                resource,
                object_id,
                actor,
                operation=action.slug,
            )
        for object_id in result.failed:
            await self._failure(
                context,
                "resource:bulk",
                resource,
                object_id,
                actor,
                "BulkActionFailed",
                operation=action.slug,
            )
        content = self._renderer.bulk_result(resource, action, result)
        return self._renderer.response(
            context,
            title=action.label,
            actor=actor,
            content=content,
        )

    async def _export_csv(self, context: Context) -> Response:
        resource = self._resource(context)
        if resource is None or resource.csv_export is None:
            return self._not_found()
        policy = resource.csv_export
        actor = await self._allowed(context, "resource:export", resource)
        if actor is None:
            await self._failure(
                context,
                "resource:export",
                resource,
                None,
                None,
                "AuthorizationDenied",
                operation="csv",
            )
            return self._forbidden()
        if (context.req.header("sec-fetch-site") or "").lower() == "cross-site":
            await self._failure(
                context,
                "resource:export",
                resource,
                None,
                actor,
                "CrossSiteRequest",
                operation="csv",
            )
            return self._forbidden()
        try:
            list_query = self._list_query(context, resource, include_pagination=False)
        except ValueError as error:
            await self._failure(
                context,
                "resource:export",
                resource,
                None,
                actor,
                "InvalidExportQuery",
                operation="csv",
            )
            return problem(400, title="Invalid admin export query", detail=str(error))
        query = ExportQuery(
            search=list_query.search,
            filters=list_query.filters,
            order_by=list_query.order_by,
            descending=list_query.descending,
            limit=policy.max_rows + 1,
            saved_view=list_query.saved_view,
        )
        await self._event(
            context,
            "attempt",
            "resource:export",
            resource,
            None,
            actor,
            operation="csv",
        )
        try:
            returned = await policy.handler(
                context,
                resource.repository_for(context),
                query,
            )
            if (
                not isinstance(returned, Sequence)
                or isinstance(returned, (str, bytes))
                or any(not isinstance(record, Mapping) for record in returned)
            ):
                raise TypeError("admin CSV export handler returned an invalid record sequence")
            records = tuple(returned)
            if len(records) > policy.max_rows:
                await self._failure(
                    context,
                    "resource:export",
                    resource,
                    None,
                    actor,
                    "ExportRowLimitExceeded",
                    operation="csv",
                )
                return problem(
                    413,
                    title="Admin CSV export exceeds its row limit",
                    detail=f"Refine the list query below {policy.max_rows} records.",
                )
            authorized_records = []
            for record in records:
                self._validate_record(resource, record)
                object_id = self._record_id(resource, record)
                if (
                    await self._allowed(
                        context,
                        "resource:export",
                        resource,
                        object_id,
                    )
                    is None
                ):
                    await self._failure(
                        context,
                        "resource:export",
                        resource,
                        object_id,
                        actor,
                        "AuthorizationDenied",
                        operation="csv",
                    )
                    return self._forbidden()
                authorized_records.append(await self._authorized_record(context, resource, record))
            body = self._csv_bytes(resource, policy, authorized_records)
        except OverflowError:
            await self._failure(
                context,
                "resource:export",
                resource,
                None,
                actor,
                "ExportByteLimitExceeded",
                operation="csv",
            )
            return problem(
                413,
                title="Admin CSV export exceeds its byte limit",
                detail=f"Refine the list query below {policy.max_bytes} bytes.",
            )
        except Exception as error:
            await self._failure(
                context,
                "resource:export",
                resource,
                None,
                actor,
                type(error).__name__,
                operation="csv",
            )
            raise
        await self._event(
            context,
            "success",
            "resource:export",
            resource,
            None,
            actor,
            operation="csv",
        )
        return context.body(
            body,
            headers={
                "cache-control": "no-store",
                "content-disposition": f'attachment; filename="{policy.filename}"',
                "content-length": str(len(body)),
                "content-security-policy": "default-src 'none'; sandbox",
                "content-type": "text/csv; charset=utf-8",
                "cross-origin-resource-policy": "same-origin",
                "referrer-policy": "no-referrer",
                "x-download-options": "noopen",
                "x-content-type-options": "nosniff",
            },
        )

    @staticmethod
    def _csv_bytes(
        resource: AdminResource,
        policy: AdminCsvExport,
        records: Sequence[Record],
    ) -> bytes:
        rows: list[bytes] = []
        total_bytes = 0
        fields = tuple(resource.field_map[name] for name in policy.fields)
        values: Sequence[Sequence[object | None]] = (
            tuple(field.label for field in fields),
            *(tuple(record.get(field.name) for field in fields) for record in records),
        )
        for row in values:
            output = io.StringIO(newline="")
            writer = csv.writer(output, lineterminator="\r\n")
            cells = tuple(_csv_cell(value) for value in row)
            if any(len(cell) > policy.max_bytes for cell in cells):
                raise OverflowError
            writer.writerow(cells)
            encoded = output.getvalue().encode("utf-8")
            total_bytes += len(encoded)
            if total_bytes > policy.max_bytes:
                raise OverflowError
            rows.append(encoded)
        return b"".join(rows)

    async def _edit_form(self, context: Context) -> Response:
        resource = self._resource(context)
        object_id = self._object_id(context)
        if resource is None or object_id is None:
            return self._not_found()
        actor = await self._allowed(context, "resource:change", resource, object_id)
        if actor is None:
            return self._forbidden()
        record = await resource.repository_for(context).get(object_id)
        if record is None:
            return self._not_found()
        self._validate_record(resource, record)
        relationship_state = await self._relationship_form_state(
            context,
            resource,
            object_id,
            record,
        )
        if relationship_state is None:
            return self._forbidden()
        values, relationship_choices = relationship_state
        action = f"{self._record_location(resource, object_id)}/edit"
        content = self._renderer.form(
            resource,
            action=action,
            heading=f"Edit {record.get(resource.title_field, object_id)}",
            values=values,
            errors={},
            submit_label="Save changes",
            relationship_choices=relationship_choices,
            source_object_id=object_id,
        )
        return self._renderer.response(
            context,
            title=f"Edit {record.get(resource.title_field, object_id)}",
            actor=actor,
            content=content,
        )

    async def _edit(self, context: Context) -> Response:
        resource = self._resource(context)
        object_id = self._object_id(context)
        if resource is None or object_id is None:
            return self._not_found()
        guard = await self._guard_mutation(context, "resource:change", resource, object_id)
        if guard is not None:
            return guard
        actor = await self._allowed(context, "resource:change", resource, object_id)
        if actor is None:
            await self._failure(
                context,
                "resource:change",
                resource,
                object_id,
                None,
                "AuthorizationDenied",
            )
            return self._forbidden()
        await self._event(context, "attempt", "resource:change", resource, object_id, actor)

        parsed = await self._parse_form(context, resource, object_id)
        if isinstance(parsed, Response):
            await self._failure(
                context,
                "resource:change",
                resource,
                object_id,
                actor,
                "InvalidForm",
            )
            return parsed
        values, display_values, errors = parsed
        action = f"{self._record_location(resource, object_id)}/edit"
        if errors:
            await self._failure(
                context,
                "resource:change",
                resource,
                object_id,
                actor,
                "ValidationError",
            )
            return await self._form_error_response(
                context,
                resource,
                actor=actor,
                action=action,
                heading=f"Edit {object_id}",
                values=display_values,
                errors=errors,
                submit_label="Save changes",
                source_object_id=object_id,
            )
        try:
            record = await resource.repository_for(context).update(object_id, values)
        except AdminValidationError as error:
            await self._failure(
                context,
                "resource:change",
                resource,
                object_id,
                actor,
                type(error).__name__,
            )
            return await self._form_error_response(
                context,
                resource,
                actor=actor,
                action=action,
                heading=f"Edit {object_id}",
                values=display_values,
                errors=self._safe_errors(resource, error.errors),
                submit_label="Save changes",
                source_object_id=object_id,
            )
        except Exception as error:
            await self._failure(
                context,
                "resource:change",
                resource,
                object_id,
                actor,
                type(error).__name__,
            )
            raise
        if record is None:
            await self._failure(
                context,
                "resource:change",
                resource,
                object_id,
                actor,
                "NotFound",
            )
            return self._not_found()
        self._validate_record(resource, record)
        await self._event(context, "success", "resource:change", resource, object_id, actor)
        return self._redirect(context, self._record_location(resource, object_id))

    async def _inline_form(self, context: Context) -> Response:
        resource = self._resource(context)
        object_id = self._object_id(context)
        if resource is None or object_id is None:
            return self._not_found()
        inline = self._inline(context, resource)
        if inline is None:
            return self._not_found()
        actor = await self._allowed(context, "resource:view", resource, object_id)
        if actor is None:
            return self._forbidden()
        parent = await resource.repository_for(context).get(object_id)
        if parent is None:
            return self._not_found()
        self._validate_record(resource, parent)
        target = self._resources[inline.target_resource]
        if await self._allowed(context, "resource:view", target) is None:
            return self._forbidden()
        collection = await self._read_inline(
            context,
            resource,
            target,
            inline,
            object_id,
        )
        if collection is None:
            return self._forbidden()
        can_change_parent = (
            await self._allowed(context, "resource:change", resource, object_id) is not None
        )
        permissions = (
            await self._inline_permissions(context, target, collection)
            if can_change_parent
            else MappingProxyType(
                {self._record_id(target, record): (False, False) for record in collection.items}
            )
        )
        can_add = (
            len(collection.items) < inline.max_items
            and can_change_parent
            and await self._allowed(context, "resource:add", target) is not None
        )
        content = self._renderer.inline_editor(
            resource,
            parent,
            target,
            inline,
            collection,
            permissions=permissions,
            can_add=can_add,
            errors={},
            error_object_id=None,
        )
        return self._renderer.response(
            context,
            title=inline.label,
            actor=actor,
            content=content,
        )

    async def _read_inline(
        self,
        context: Context,
        resource: AdminResource,
        target: AdminResource,
        inline: AdminInline,
        object_id: str,
    ) -> InlineCollection | None:
        collection = await inline.read(
            context,
            resource,
            target,
            inline,
            object_id,
            inline.max_items,
        )
        if not isinstance(collection, InlineCollection):
            raise TypeError("inline reader returned an invalid collection")
        if collection.total > inline.max_items:
            raise ValueError("inline reader exceeded the declared maximum")
        seen: set[str] = set()
        for record in collection.items:
            self._validate_record(target, record)
            child_id = self._record_id(target, record)
            if child_id in seen:
                raise ValueError("inline reader returned duplicate object IDs")
            seen.add(child_id)
            parent_id = record.get(inline.parent_field)
            if parent_id is None or str(parent_id) != object_id:
                raise ValueError("inline reader returned a record for another parent")
            if await self._allowed(context, "resource:view", target, child_id) is None:
                return None
        return collection

    async def _inline_permissions(
        self,
        context: Context,
        target: AdminResource,
        collection: InlineCollection,
    ) -> Mapping[str, tuple[bool, bool]]:
        permissions = {}
        for record in collection.items:
            object_id = self._record_id(target, record)
            permissions[object_id] = (
                await self._allowed(context, "resource:change", target, object_id) is not None,
                await self._allowed(context, "resource:delete", target, object_id) is not None,
            )
        return MappingProxyType(permissions)

    async def _inline_mutation(self, context: Context) -> Response:
        resource = self._resource(context)
        object_id = self._object_id(context)
        if resource is None or object_id is None:
            return self._not_found()
        inline = self._inline(context, resource)
        if inline is None:
            return self._not_found()
        guard = await self._guard_mutation(
            context,
            "resource:change",
            resource,
            object_id,
        )
        if guard is not None:
            return guard
        actor = await self._allowed(context, "resource:change", resource, object_id)
        if actor is None:
            await self._failure(
                context,
                "resource:change",
                resource,
                object_id,
                None,
                "AuthorizationDenied",
                operation=f"inline:{inline.slug}",
            )
            return self._forbidden()
        parent = await resource.repository_for(context).get(object_id)
        if parent is None:
            return self._not_found()
        self._validate_record(resource, parent)
        target = self._resources[inline.target_resource]
        if await self._allowed(context, "resource:view", target) is None:
            return self._forbidden()
        collection = await self._read_inline(
            context,
            resource,
            target,
            inline,
            object_id,
        )
        if collection is None:
            await self._failure(
                context,
                "resource:change",
                target,
                None,
                actor,
                "AuthorizationDenied",
                operation=f"inline:{resource.slug}:{inline.slug}",
            )
            return self._forbidden()
        parsed = await self._parse_inline_form(
            context,
            target,
            inline,
            collection,
        )
        if isinstance(parsed, Response):
            await self._failure(
                context,
                "resource:change",
                target,
                None,
                actor,
                "InvalidInlineForm",
                operation=f"inline:{resource.slug}:{inline.slug}",
            )
            return parsed
        mutation, display_values, errors = parsed
        if errors:
            if mutation.operation == "create":
                invalid_action: AdminAction = "resource:add"
            elif mutation.operation == "update":
                invalid_action = "resource:change"
            else:
                invalid_action = "resource:delete"
            await self._failure(
                context,
                invalid_action,
                target,
                mutation.object_id,
                actor,
                "InvalidInlineForm",
                operation=f"inline:{resource.slug}:{inline.slug}",
            )
            return await self._inline_error_response(
                context,
                actor,
                resource,
                parent,
                target,
                inline,
                collection,
                mutation,
                display_values,
                errors,
            )
        if mutation.operation == "create":
            action: AdminAction = "resource:add"
        elif mutation.operation == "update":
            action = "resource:change"
        else:
            action = "resource:delete"
        if await self._allowed(context, action, target, mutation.object_id) is None:
            await self._failure(
                context,
                action,
                target,
                mutation.object_id,
                actor,
                "AuthorizationDenied",
                operation=f"inline:{resource.slug}:{inline.slug}",
            )
            return self._forbidden()
        operation = f"inline:{resource.slug}:{inline.slug}"
        await self._event(
            context,
            "attempt",
            action,
            target,
            mutation.object_id,
            actor,
            operation=operation,
        )
        try:
            result = await inline.mutate(
                context,
                resource,
                target,
                inline,
                object_id,
                mutation,
            )
            result_id = self._validate_inline_result(
                target,
                inline,
                object_id,
                mutation,
                result,
            )
        except AdminValidationError as error:
            await self._failure(
                context,
                action,
                target,
                mutation.object_id,
                actor,
                type(error).__name__,
                operation=operation,
            )
            return await self._inline_error_response(
                context,
                actor,
                resource,
                parent,
                target,
                inline,
                collection,
                mutation,
                display_values,
                self._safe_inline_errors(target, inline, error.errors),
            )
        except Exception as error:
            await self._failure(
                context,
                action,
                target,
                mutation.object_id,
                actor,
                type(error).__name__,
                operation=operation,
            )
            raise
        await self._event(
            context,
            "success",
            action,
            target,
            result_id,
            actor,
            operation=operation,
        )
        return self._redirect(
            context,
            f"{self._record_location(resource, object_id)}/inline/{inline.slug}",
        )

    async def _parse_inline_form(
        self,
        context: Context,
        target: AdminResource,
        inline: AdminInline,
        collection: InlineCollection,
    ) -> tuple[InlineMutation, Mapping[str, object], Mapping[str, str]] | Response:
        content_type = (context.req.header("content-type") or "").partition(";")[0].strip().lower()
        if content_type != "application/x-www-form-urlencoded":
            return problem(415, title="Admin forms require application/x-www-form-urlencoded")
        limits = FormDataLimits(
            max_body_bytes=_FORM_BODY_LIMIT,
            max_file_bytes=0,
            max_field_bytes=16 * 1024,
            max_parts=len(inline.fields) + 3,
            max_header_bytes=8 * 1024,
            file_memory_bytes=0,
        )
        try:
            form = await context.req.form_data(limits)
        except (FormDataLimitError, TypeError) as form_error:
            return problem(413, title="Admin inline form rejected", detail=str(form_error))

        allowed = set(inline.fields) | {"operation", "object_id"}
        raw: dict[str, str] = {}
        errors: dict[str, str] = {}
        async with form:
            for name, value in form:
                if name not in allowed:
                    errors["__all__"] = "The inline form contains an unexpected field."
                    continue
                if name in raw:
                    errors[name if name in inline.fields else "__all__"] = (
                        "Submit exactly one value for each inline field."
                    )
                    continue
                if isinstance(value, File):
                    errors[name if name in inline.fields else "__all__"] = (
                        "File uploads are not supported by inline fields."
                    )
                    continue
                raw[name] = value

        raw_operation = raw.get("operation")
        object_id = raw.get("object_id") or None
        if raw_operation == "update":
            operation: InlineOperation = "update"
        elif raw_operation == "delete":
            operation = "delete"
        else:
            operation = "create"
        if raw_operation not in ("create", "update", "delete"):
            errors["__all__"] = "Choose one inline operation."
            object_id = None
        existing = {self._record_id(target, record): record for record in collection.items}
        if operation in ("update", "delete") and object_id not in existing:
            errors["__all__"] = "The inline record does not belong to this parent."
            if object_id is None:
                object_id = "__missing__"
        if operation == "create" and object_id is not None:
            errors["__all__"] = "Inline create must not include an object ID."
            object_id = None
        if operation == "create" and collection.total >= inline.max_items:
            errors["__all__"] = f"At most {inline.max_items} inline records are allowed."

        values: dict[str, object] = {}
        display_values: dict[str, object] = dict(raw)
        if operation != "delete":
            for field_name in inline.fields:
                admin_field = target.field_map[field_name]
                parsed_value, parse_error = admin_field.parse(raw.get(field_name))
                if admin_field.kind == "checkbox":
                    display_values[field_name] = bool(parsed_value)
                if parse_error is not None:
                    errors[field_name] = parse_error
                elif parsed_value is not None:
                    values[field_name] = parsed_value
        mutation = InlineMutation(
            operation=operation,
            object_id=object_id,
            values={} if operation == "delete" else values,
        )
        return mutation, MappingProxyType(display_values), MappingProxyType(errors)

    async def _inline_error_response(
        self,
        context: Context,
        actor: Actor,
        resource: AdminResource,
        parent: Record,
        target: AdminResource,
        inline: AdminInline,
        collection: InlineCollection,
        mutation: InlineMutation,
        display_values: Mapping[str, object],
        errors: Mapping[str, str],
    ) -> Response:
        permissions = await self._inline_permissions(context, target, collection)
        can_add = (
            collection.total < inline.max_items
            and await self._allowed(context, "resource:add", target) is not None
        )
        content = self._renderer.inline_editor(
            resource,
            parent,
            target,
            inline,
            collection,
            permissions=permissions,
            can_add=can_add,
            errors=errors,
            error_object_id=mutation.object_id,
            error_values=display_values,
            error_operation=mutation.operation,
        )
        return self._renderer.response(
            context,
            title=inline.label,
            actor=actor,
            content=content,
            status=422,
        )

    @staticmethod
    def _safe_inline_errors(
        target: AdminResource,
        inline: AdminInline,
        errors: Mapping[str, str],
    ) -> Mapping[str, str]:
        allowed = set(inline.fields) | {"__all__"}
        safe = {
            name if name in allowed else "__all__": message
            for name, message in errors.items()
            if message
        }
        return safe or {"__all__": "The inline record could not be saved."}

    @classmethod
    def _validate_inline_result(
        cls,
        target: AdminResource,
        inline: AdminInline,
        parent_object_id: str,
        mutation: InlineMutation,
        result: InlineMutationResult,
    ) -> str:
        if not isinstance(result, InlineMutationResult):
            raise TypeError("inline mutator returned an invalid result")
        if mutation.operation == "delete":
            if not result.deleted or result.record is not None:
                raise ValueError("inline delete did not confirm one deletion")
            if mutation.object_id is None:
                raise ValueError("inline delete result has no object ID")
            return mutation.object_id
        if result.deleted or result.record is None:
            raise ValueError("inline create/update did not return a record")
        cls._validate_record(target, result.record)
        if str(result.record.get(inline.parent_field)) != parent_object_id:
            raise ValueError("inline mutator returned a record for another parent")
        result_id = cls._record_id(target, result.record)
        if mutation.operation == "update" and result_id != mutation.object_id:
            raise ValueError("inline update returned another object")
        return result_id

    async def _delete_form(self, context: Context) -> Response:
        resource = self._resource(context)
        object_id = self._object_id(context)
        if resource is None or object_id is None:
            return self._not_found()
        actor = await self._allowed(context, "resource:delete", resource, object_id)
        if actor is None:
            return self._forbidden()
        record = await resource.repository_for(context).get(object_id)
        if record is None:
            return self._not_found()
        self._validate_record(resource, record)
        action = f"{self._record_location(resource, object_id)}/delete"
        content = self._renderer.delete_confirmation(resource, record, action=action)
        return self._renderer.response(
            context,
            title=f"Delete {record.get(resource.title_field, object_id)}",
            actor=actor,
            content=content,
        )

    async def _delete(self, context: Context) -> Response:
        resource = self._resource(context)
        object_id = self._object_id(context)
        if resource is None or object_id is None:
            return self._not_found()
        guard = await self._guard_mutation(context, "resource:delete", resource, object_id)
        if guard is not None:
            return guard
        actor = await self._allowed(context, "resource:delete", resource, object_id)
        if actor is None:
            await self._failure(
                context,
                "resource:delete",
                resource,
                object_id,
                None,
                "AuthorizationDenied",
            )
            return self._forbidden()
        await self._event(context, "attempt", "resource:delete", resource, object_id, actor)
        try:
            deleted = await resource.repository_for(context).delete(object_id)
        except Exception as error:
            await self._failure(
                context,
                "resource:delete",
                resource,
                object_id,
                actor,
                type(error).__name__,
            )
            raise
        if not deleted:
            await self._failure(
                context,
                "resource:delete",
                resource,
                object_id,
                actor,
                "NotFound",
            )
            return self._not_found()
        await self._event(context, "success", "resource:delete", resource, object_id, actor)
        return self._redirect(context, f"{self.prefix}/{resource.slug}")

    async def _guard_mutation(
        self,
        context: Context,
        action: AdminAction,
        resource: AdminResource,
        object_id: str | None,
    ) -> Response | None:
        fetch_site = (context.req.header("sec-fetch-site") or "").lower()
        if fetch_site not in ("", "same-origin", "same-site", "none"):
            await self._failure(
                context,
                action,
                resource,
                object_id,
                None,
                "CrossSiteRequest",
            )
            return problem(403, title="Cross-site admin mutation rejected")
        origin = context.req.header("origin")
        try:
            normalized = None if origin is None else _normalize_origin(origin)
        except ValueError:
            normalized = None
        if normalized not in self._trusted_origins:
            await self._failure(context, action, resource, object_id, None, "InvalidOrigin")
            return problem(403, title="Admin mutation origin rejected")
        return None

    async def _parse_form(
        self,
        context: Context,
        resource: AdminResource,
        source_object_id: str | None,
    ) -> tuple[Mapping[str, object], Mapping[str, object], Mapping[str, str]] | Response:
        content_type = (context.req.header("content-type") or "").partition(";")[0].strip().lower()
        if content_type != "application/x-www-form-urlencoded":
            return problem(415, title="Admin forms require application/x-www-form-urlencoded")
        limits = FormDataLimits(
            max_body_bytes=_FORM_BODY_LIMIT,
            max_file_bytes=0,
            max_field_bytes=16 * 1024,
            max_parts=len(resource.fields) + 2,
            max_header_bytes=8 * 1024,
            file_memory_bytes=0,
        )
        try:
            form = await context.req.form_data(limits)
        except (FormDataLimitError, TypeError) as form_error:
            return problem(413, title="Admin form rejected", detail=str(form_error))

        allowed = {field.name for field in resource.fields if not field.read_only}
        raw: dict[str, str] = {}
        errors: dict[str, str] = {}
        async with form:
            for name, value in form:
                if name not in allowed:
                    errors["__all__"] = "The form contains an unexpected field."
                    continue
                if name in raw:
                    errors[name] = "Submit exactly one value for this field."
                    continue
                if isinstance(value, File):
                    errors[name] = "File uploads are not supported by this field."
                    continue
                raw[name] = value

        values: dict[str, object] = {}
        display_values: dict[str, object] = dict(raw)
        for admin_field in resource.fields:
            if admin_field.read_only:
                continue
            parsed_value, parse_error = admin_field.parse(raw.get(admin_field.name))
            if admin_field.kind == "checkbox":
                display_values[admin_field.name] = bool(parsed_value)
            if parse_error is not None:
                errors[admin_field.name] = parse_error
            elif parsed_value is not None:
                values[admin_field.name] = parsed_value
        for relationship in resource.relationships:
            if relationship.field in errors:
                continue
            related_id = values.get(relationship.field)
            if related_id is None:
                display_values[relationship.display_field] = None
                continue
            choice = await self._resolve_relationship(
                context,
                resource,
                relationship,
                source_object_id,
                str(related_id),
            )
            if choice is None:
                values.pop(relationship.field, None)
                errors[relationship.field] = "Select an authorized related record."
                continue
            values[relationship.field] = choice.id
            display_values[relationship.field] = choice.id
            display_values[relationship.display_field] = choice.label
        return (
            MappingProxyType(values),
            MappingProxyType(display_values),
            MappingProxyType(errors),
        )

    async def _parse_bulk_form(
        self,
        context: Context,
        resource: AdminResource,
        actor: Actor,
    ) -> tuple[AdminBulkAction, tuple[str, ...]] | Response:
        content_type = (context.req.header("content-type") or "").partition(";")[0].strip().lower()
        if content_type != "application/x-www-form-urlencoded":
            return problem(415, title="Admin forms require application/x-www-form-urlencoded")
        limits = FormDataLimits(
            max_body_bytes=_FORM_BODY_LIMIT,
            max_file_bytes=0,
            max_field_bytes=512,
            max_parts=101,
            max_header_bytes=8 * 1024,
            file_memory_bytes=0,
        )
        try:
            form = await context.req.form_data(limits)
        except (FormDataLimitError, TypeError) as form_error:
            return problem(413, title="Admin bulk form rejected", detail=str(form_error))

        action_slug: str | None = None
        object_ids: list[str] = []
        error: str | None = None
        async with form:
            for name, value in form:
                if isinstance(value, File):
                    error = "File uploads are not accepted by bulk actions."
                elif name == "action":
                    if action_slug is not None:
                        error = "Submit exactly one bulk action."
                    else:
                        action_slug = value
                elif name == "selected":
                    if (
                        not value
                        or len(value) > 255
                        or any(ord(character) < 0x20 for character in value)
                    ):
                        error = "Selected object IDs must be bounded printable strings."
                    else:
                        object_ids.append(value)
                else:
                    error = "The bulk form contains an unexpected field."

        if error is None and action_slug is None:
            error = "Choose a bulk action."
        action = None if action_slug is None else resource.bulk_action_map.get(action_slug)
        if error is None and action is None:
            error = "Choose a registered bulk action."
        unique_ids = tuple(dict.fromkeys(object_ids))
        if error is None and not unique_ids:
            error = "Select at least one record."
        if error is None and action is not None and len(object_ids) > action.max_selected:
            error = f"Select at most {action.max_selected} records."
        if error is not None or action is None:
            content = self._renderer.bulk_error(resource, error or "The bulk form is invalid.")
            return self._renderer.response(
                context,
                title="Bulk action rejected",
                actor=actor,
                content=content,
                status=422,
            )
        return action, unique_ids

    async def _form_error_response(
        self,
        context: Context,
        resource: AdminResource,
        *,
        actor: Actor,
        action: str,
        heading: str,
        values: Mapping[str, object],
        errors: Mapping[str, str],
        submit_label: str,
        source_object_id: str | None,
    ) -> Response:
        relationship_values = dict(values)
        for relationship in resource.relationships:
            if relationship.field in errors:
                relationship_values.pop(relationship.field, None)
                relationship_values.pop(relationship.display_field, None)
        relationship_state = await self._relationship_form_state(
            context,
            resource,
            source_object_id,
            relationship_values,
        )
        if relationship_state is None:
            return self._forbidden()
        values, relationship_choices = relationship_state
        content = self._renderer.form(
            resource,
            action=action,
            heading=heading,
            values=values,
            errors=errors,
            submit_label=submit_label,
            relationship_choices=relationship_choices,
            source_object_id=source_object_id,
        )
        return self._renderer.response(
            context,
            title=heading,
            actor=actor,
            content=content,
            status=422,
        )

    @staticmethod
    def _safe_errors(resource: AdminResource, errors: Mapping[str, str]) -> Mapping[str, str]:
        allowed = set(resource.field_map) | {"__all__"}
        safe = {
            name if name in allowed else "__all__": message
            for name, message in errors.items()
            if message
        }
        return safe or {"__all__": "The record could not be saved."}

    @staticmethod
    def _validate_bulk_result(
        selected: tuple[str, ...],
        result: BulkActionResult,
    ) -> None:
        if not isinstance(result, BulkActionResult):
            raise TypeError("admin bulk action returned an invalid result")
        returned = tuple(result.succeeded) + tuple(result.failed)
        if len(returned) != len(selected) or set(returned) != set(selected):
            raise ValueError("admin bulk action result must partition every selected object")

    @staticmethod
    def _validate_history_page(
        resource: AdminResource,
        object_id: str,
        page: AuditHistoryPage,
        limit: int,
    ) -> None:
        if not isinstance(page, AuditHistoryPage):
            raise TypeError("admin history reader returned an invalid page")
        if len(page.items) > limit:
            raise ValueError("admin history reader returned more than the requested limit")
        if any(
            event.resource != resource.slug or event.object_id != object_id for event in page.items
        ):
            raise ValueError("admin history reader returned an event for another object")

    @staticmethod
    def _record_id(resource: AdminResource, record: Record) -> str:
        value = record.get(resource.id_field)
        if value is None:
            raise ValueError(f"{resource.slug}: created record is missing its ID")
        return str(value)

    def _record_location(self, resource: AdminResource, object_id: str) -> str:
        return f"{self.prefix}/{resource.slug}/object/{quote(object_id, safe='')}"

    @staticmethod
    def _redirect(context: Context, location: str) -> Response:
        if HtmxRequest.from_context(context).is_htmx:
            return with_htmx(context.body(None, 204), redirect=location)
        return context.redirect(location, 303)

    async def _event(
        self,
        context: Context,
        phase: AuditPhase,
        action: AdminAction,
        resource: AdminResource,
        object_id: str | None,
        actor: Actor | None,
        error_type: str | None = None,
        operation: str | None = None,
    ) -> None:
        sink = self._audit
        if sink is None:
            factory = self._audit_factory
            if factory is None:
                raise RuntimeError("admin audit configuration is missing")
            sink = factory(context)
        if not callable(sink):
            raise TypeError("admin audit_factory returned an invalid sink")
        await sink(
            AuditEvent(
                occurred_at=datetime.now(UTC),
                phase=phase,
                action=action,
                resource=resource.slug,
                object_id=object_id,
                actor_id=None if actor is None else actor.id,
                error_type=error_type,
                operation=operation,
            )
        )

    async def _failure(
        self,
        context: Context,
        action: AdminAction,
        resource: AdminResource,
        object_id: str | None,
        actor: Actor | None,
        error_type: str,
        *,
        operation: str | None = None,
    ) -> None:
        await self._event(
            context,
            "failure",
            action,
            resource,
            object_id,
            actor,
            error_type,
            operation,
        )
