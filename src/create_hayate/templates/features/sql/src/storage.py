"""Checked SQL storage: SQLite on ASGI, D1 on Cloudflare Workers."""

from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from hayate import Context
from hayate_sql import Database
from hayate_sql.adapters import D1Database, SQLiteDatabase

import queries


class Todo(TypedDict):
    id: str
    title: str
    done: bool


_sqlite: SQLiteDatabase | None = None


def database(c: Context) -> Database:
    """Resolve one request database with consistent D1 session reads."""
    binding = getattr(c.env, "DB", None) if c.env is not None else None
    if binding is not None:
        return D1Database(binding).with_session("first-primary")

    global _sqlite
    if _sqlite is None:
        _sqlite = SQLiteDatabase(Path("app.db"))
        migrations = Path(__file__).resolve().parents[1] / "migrations"
        for migration in sorted(migrations.glob("*.sql")):
            _sqlite.raw.executescript(migration.read_text(encoding="utf-8"))
    return _sqlite


def _todo(row: queries.GetTodoRow | queries.ListTodosRow) -> Todo:
    return Todo(id=row["id"], title=row["title"], done=bool(row["done"]))


async def list_todos(c: Context, owner: str) -> list[Todo]:
    rows = await queries.list_todos(database(c), owner=owner)
    return [_todo(row) for row in rows]


async def create_todo(c: Context, owner: str, title: str) -> Todo:
    todo = Todo(id=str(uuid4()), title=title, done=False)
    await queries.create_todo(
        database(c),
        todo_id=todo["id"],
        owner=owner,
        title=title,
    )
    return todo


async def get_todo(c: Context, owner: str, todo_id: str) -> Todo | None:
    row = await queries.get_todo(database(c), owner=owner, todo_id=todo_id)
    return None if row is None else _todo(row)


async def update_todo(
    c: Context,
    owner: str,
    todo_id: str,
    title: str,
) -> Todo | None:
    result = await queries.update_todo(
        database(c),
        owner=owner,
        todo_id=todo_id,
        title=title,
    )
    return None if result.rows_affected != 1 else await get_todo(c, owner, todo_id)


async def toggle_todo(c: Context, owner: str, todo_id: str) -> Todo | None:
    result = await queries.toggle_todo(
        database(c),
        owner=owner,
        todo_id=todo_id,
    )
    return None if result.rows_affected != 1 else await get_todo(c, owner, todo_id)


async def delete_todo(c: Context, owner: str, todo_id: str) -> bool:
    result = await queries.delete_todo(database(c), owner=owner, todo_id=todo_id)
    return result.rows_affected == 1
