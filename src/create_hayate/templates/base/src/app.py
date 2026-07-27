"""$project_name: one Hayate application core for every supported runtime."""

from uuid import UUID

from hayate import URL, Context, Hayate, HTTPException

from contracts import describe, validated
from generated_features import register_features
from identity import principal, subject
from runtime import LOCAL_ENV
from storage import create_todo, delete_todo, get_todo, list_todos

app = Hayate(env=LOCAL_ENV)

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


@app.get("/health")
@describe(summary="Health check", response={"type": "object"}, operation_id="health")
async def health(c: Context):
    return c.json({"status": "ok"})


@app.get("/canonicalize")
@describe(summary="Canonicalize an international hostname", operation_id="canonicalize")
async def canonicalize(c: Context):
    return c.json({"hostname": URL("https://日本語.example/").hostname})


@app.get("/whoami")
@describe(summary="Current request identity", response={"type": "object"}, operation_id="whoami")
async def whoami(c: Context):
    return c.json(principal(c))


@app.get("/todos")
@describe(
    summary="List todos",
    response={"type": "array", "items": TODO_SCHEMA},
    operation_id="listTodos",
)
async def todos_index(c: Context):
    return c.json(await list_todos(c, subject(c)))


@app.post("/todos", validated("json", TODO_CREATE_SCHEMA))
@describe(
    summary="Create a todo",
    status=201,
    response=TODO_SCHEMA,
    responses={400: None},
    operation_id="createTodo",
)
async def todos_create(c: Context):
    data = c.req.valid("json")
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise HTTPException(400, title="title must be a non-empty string up to 200 characters")
    todo = await create_todo(c, subject(c), title.strip())
    return c.json(todo, status=201)


@app.get("/todos/:id", validated("param", TODO_ID_SCHEMA))
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


@app.delete("/todos/:id", validated("param", TODO_ID_SCHEMA))
@describe(summary="Delete a todo", status=204, responses={404: None}, operation_id="deleteTodo")
async def todos_delete(c: Context):
    if not await delete_todo(c, subject(c), _validated_todo_id(c)):
        raise HTTPException(404, title="Todo not found")
    return c.body(None, status=204)


register_features(app)
