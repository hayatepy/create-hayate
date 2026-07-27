"""Context-first TODO JSON API used without the OpenAPI feature."""

from uuid import UUID

from hayate import Context, Hayate, HTTPException

from contracts import describe, validated
from identity import subject
from storage import create_todo, delete_todo, get_todo, list_todos, update_todo
from todo_domain import InvalidTodoTitle, normalize_title

TODO_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "done": {"type": "boolean"},
    },
    "required": ["id", "title", "done"],
    "additionalProperties": False,
}
TODO_CREATE_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string", "minLength": 1, "maxLength": 200}},
    "required": ["title"],
    "additionalProperties": False,
}
TODO_ID_SCHEMA = {
    "type": "object",
    "properties": {"id": {"type": "string", "format": "uuid"}},
    "required": ["id"],
    "additionalProperties": False,
}


def _validated_todo_id(c: Context) -> str:
    value = c.req.valid("param").get("id")
    try:
        if not isinstance(value, str):
            raise ValueError
        UUID(value)
        if not all(value[position] == "-" for position in (8, 13, 18, 23)):
            raise ValueError
    except (ValueError, IndexError):
        raise HTTPException(
            400,
            title="Validation failed",
            detail="$$.id: value must be a hyphenated UUID",
        ) from None
    return value


def register(app: Hayate) -> None:
    @app.get("$api_prefix/todos")
    @describe(
        summary="List todos",
        response={"type": "array", "items": TODO_SCHEMA},
        operation_id="listTodos",
    )
    async def todos_index(c: Context):
        return c.json(await list_todos(c, subject(c)))

    @app.post("$api_prefix/todos", validated("json", TODO_CREATE_SCHEMA))
    @describe(
        summary="Create a todo",
        status=201,
        response=TODO_SCHEMA,
        responses={400: None},
        operation_id="createTodo",
    )
    async def todos_create(c: Context):
        data = c.req.valid("json")
        try:
            title = normalize_title(data.get("title") if isinstance(data, dict) else None)
        except InvalidTodoTitle as exc:
            raise HTTPException(400, title=str(exc)) from exc
        todo = await create_todo(c, subject(c), title)
        return c.json(todo, status=201)

    @app.get("$api_prefix/todos/:id", validated("param", TODO_ID_SCHEMA))
    @describe(
        summary="Get a todo",
        response=TODO_SCHEMA,
        responses={404: None},
        operation_id="getTodo",
    )
    async def todos_show(c: Context):
        todo = await get_todo(c, subject(c), _validated_todo_id(c))
        if todo is None:
            raise HTTPException(404, title="Todo not found")
        return c.json(todo)

    @app.patch(
        "$api_prefix/todos/:id",
        validated("param", TODO_ID_SCHEMA),
        validated("json", TODO_CREATE_SCHEMA),
    )
    @describe(
        summary="Update a todo",
        response=TODO_SCHEMA,
        responses={400: None, 404: None},
        operation_id="updateTodo",
    )
    async def todos_update(c: Context):
        data = c.req.valid("json")
        try:
            title = normalize_title(data.get("title") if isinstance(data, dict) else None)
        except InvalidTodoTitle as exc:
            raise HTTPException(400, title=str(exc)) from exc
        todo = await update_todo(c, subject(c), _validated_todo_id(c), title)
        if todo is None:
            raise HTTPException(404, title="Todo not found")
        return c.json(todo)

    @app.delete("$api_prefix/todos/:id", validated("param", TODO_ID_SCHEMA))
    @describe(
        summary="Delete a todo",
        status=204,
        responses={404: None},
        operation_id="deleteTodo",
    )
    async def todos_delete(c: Context):
        if not await delete_todo(c, subject(c), _validated_todo_id(c)):
            raise HTTPException(404, title="Todo not found")
        return c.body(None, status=204)
