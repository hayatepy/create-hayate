"""Typed TODO JSON API with one runtime and OpenAPI response contract."""

from typing import Annotated, TypedDict
from uuid import UUID

from hayate import Context, Hayate, HTTPException
from hayate_openapi import Path, StdlibProvider, endpoint, validated

from identity import subject
from storage import Todo, create_todo, delete_todo, get_todo, list_todos, update_todo
from todo_domain import InvalidTodoTitle, normalize_title

TODO_CREATE_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string", "minLength": 1, "maxLength": 200}},
    "required": ["title"],
    "additionalProperties": False,
}
_PROVIDERS = [StdlibProvider()]


class TodoResponse(TypedDict):
    id: UUID
    title: str
    done: bool


def _response(todo: Todo) -> TodoResponse:
    return {
        "id": UUID(todo["id"]),
        "title": todo["title"],
        "done": todo["done"],
    }


def register(app: Hayate) -> None:
    @app.get("$api_prefix/todos")
    @endpoint(
        summary="List todos",
        operation_id="listTodos",
        providers=_PROVIDERS,
    )
    async def todos_index(c: Context) -> list[TodoResponse]:
        return [_response(todo) for todo in await list_todos(c, subject(c))]

    @app.post("$api_prefix/todos", validated("json", TODO_CREATE_SCHEMA))
    @endpoint(
        status=201,
        summary="Create a todo",
        responses={400: None},
        operation_id="createTodo",
        providers=_PROVIDERS,
    )
    async def todos_create(c: Context) -> TodoResponse:
        data = c.req.valid("json")
        try:
            title = normalize_title(data.get("title") if isinstance(data, dict) else None)
        except InvalidTodoTitle as exc:
            raise HTTPException(400, title=str(exc)) from exc
        return _response(await create_todo(c, subject(c), title))

    @app.get("$api_prefix/todos/:id")
    @endpoint(
        summary="Get a todo",
        responses={404: None},
        operation_id="getTodo",
        providers=_PROVIDERS,
    )
    async def todos_show(
        c: Context,
        todo_id: Annotated[UUID, Path(alias="id")],
    ) -> TodoResponse:
        todo = await get_todo(c, subject(c), str(todo_id))
        if todo is None:
            raise HTTPException(404, title="Todo not found")
        return _response(todo)

    @app.patch(
        "$api_prefix/todos/:id",
        validated("json", TODO_CREATE_SCHEMA),
    )
    @endpoint(
        summary="Update a todo",
        responses={400: None, 404: None},
        operation_id="updateTodo",
        providers=_PROVIDERS,
    )
    async def todos_update(
        c: Context,
        todo_id: Annotated[UUID, Path(alias="id")],
    ) -> TodoResponse:
        data = c.req.valid("json")
        try:
            title = normalize_title(data.get("title") if isinstance(data, dict) else None)
        except InvalidTodoTitle as exc:
            raise HTTPException(400, title=str(exc)) from exc
        todo = await update_todo(c, subject(c), str(todo_id), title)
        if todo is None:
            raise HTTPException(404, title="Todo not found")
        return _response(todo)

    @app.delete("$api_prefix/todos/:id")
    @endpoint(
        status=204,
        summary="Delete a todo",
        responses={404: None},
        operation_id="deleteTodo",
        providers=_PROVIDERS,
    )
    async def todos_delete(
        c: Context,
        todo_id: Annotated[UUID, Path(alias="id")],
    ) -> None:
        if not await delete_todo(c, subject(c), str(todo_id)):
            raise HTTPException(404, title="Todo not found")
