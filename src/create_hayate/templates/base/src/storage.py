"""In-memory storage component used when the sql feature is absent."""

from typing import TypedDict
from uuid import uuid4

from hayate import Context


class Todo(TypedDict):
    id: str
    title: str
    done: bool


_TODOS: dict[tuple[str, str], Todo] = {}


async def list_todos(_c: Context, owner: str) -> list[Todo]:
    return [todo for (subject, _), todo in _TODOS.items() if subject == owner]


async def create_todo(_c: Context, owner: str, title: str) -> Todo:
    todo = Todo(id=str(uuid4()), title=title, done=False)
    _TODOS[(owner, todo["id"])] = todo
    return todo


async def get_todo(_c: Context, owner: str, todo_id: str) -> Todo | None:
    return _TODOS.get((owner, todo_id))


async def update_todo(_c: Context, owner: str, todo_id: str, title: str) -> Todo | None:
    todo = _TODOS.get((owner, todo_id))
    if todo is not None:
        todo["title"] = title
    return todo


async def toggle_todo(_c: Context, owner: str, todo_id: str) -> Todo | None:
    todo = _TODOS.get((owner, todo_id))
    if todo is not None:
        todo["done"] = not todo["done"]
    return todo


async def delete_todo(_c: Context, owner: str, todo_id: str) -> bool:
    return _TODOS.pop((owner, todo_id), None) is not None
