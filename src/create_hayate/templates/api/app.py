"""$project_name: a TODO API on hayate.

Request/Response follow WHATWG Fetch semantics, so this app is a pure
``fetch(Request) -> Response`` core: any ASGI server runs it, and the same
file works on Cloudflare Python Workers unchanged.
"""

from hayate import Context, Hayate, HTTPException

app = Hayate()

TODOS: dict[str, dict] = {}
_serial = 0


def _next_id() -> str:
    global _serial
    _serial += 1
    return str(_serial)


@app.get("/todos")
async def list_todos(c: Context):
    return c.json(list(TODOS.values()))


@app.post("/todos")
async def create_todo(c: Context):
    data = await c.req.json()
    if not isinstance(data, dict) or not isinstance(data.get("title"), str):
        raise HTTPException(400, title="Body must be a JSON object with a string 'title'")
    todo = {"id": _next_id(), "title": data["title"], "done": False}
    TODOS[todo["id"]] = todo
    return c.json(todo, status=201)


@app.get("/todos/:id")
async def show_todo(c: Context):
    todo = TODOS.get(c.req.param("id"))
    if todo is None:
        raise HTTPException(404, title="Todo not found")
    return c.json(todo)


@app.delete("/todos/:id")
async def delete_todo(c: Context):
    if TODOS.pop(c.req.param("id"), None) is None:
        raise HTTPException(404, title="Todo not found")
    return c.body(None, status=204)
