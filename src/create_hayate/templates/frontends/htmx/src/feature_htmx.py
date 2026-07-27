"""Server-owned HTML transport for the generated Hayate application."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from hayate import Context, Hayate, HTTPException, Next, Response, SSEMessage
from hayate.middleware import static_files
$htmx_import_block
from identity import principal, subject
from storage import create_todo, delete_todo, get_todo, list_todos, toggle_todo, update_todo
from todo_domain import InvalidTodoTitle, normalize_title

_ROOT = Path(__file__).resolve().parents[1]
_FILTERS = frozenset({"all", "open", "done"})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self'"
)


def _selected_filter(c: Context) -> str:
    value = c.req.query("filter") or "all"
    return value if value in _FILTERS else "all"


async def _page_values(c: Context) -> dict[str, object]:
    selected = _selected_filter(c)
    todos = await list_todos(c, subject(c))
    if selected == "open":
        todos = [todo for todo in todos if not todo["done"]]
    elif selected == "done":
        todos = [todo for todo in todos if todo["done"]]
    return {
        "current_filter": selected,
        "principal": principal(c),
        "todos": todos,
    }


def _csrf_allowed(c: Context) -> bool:
    if c.req.method in _SAFE_METHODS:
        return True
    origin = c.req.header("origin")
    if origin is not None and origin != "null":
        return origin == c.req.url.origin
    fetch_site = c.req.header("sec-fetch-site")
    return fetch_site in (None, "same-origin", "none")


async def _csrf_guard(c: Context, next_: Next) -> None:
    if not _csrf_allowed(c):
        raise HTTPException(403, title="Cross-origin request rejected")
    await next_()


async def _security_headers(c: Context, next_: Next) -> None:
    await next_()
    response = c.res
    if response is None:
        return
    response.headers.set("content-security-policy", _CSP)
    response.headers.set("permissions-policy", "camera=(), microphone=(), geolocation=()")
    response.headers.set("referrer-policy", "same-origin")
    response.headers.set("x-content-type-options", "nosniff")
    pathname = c.req.url.pathname
    if pathname.startswith("/assets/vendor/"):
        response.headers.set("cache-control", "public, max-age=31536000, immutable")
    elif pathname == "/auth" or pathname == "/app" or pathname.startswith("/app/"):
        response.headers.set("cache-control", "private, no-store")


def register(app: Hayate) -> None:
$htmx_renderer_setup
    pages = HtmxTemplates(renderer)

    app.use(_security_headers)
    app.use(
        "/assets/*",
        static_files(root=_ROOT / "public" / "assets", strip_prefix="/assets"),
    )

    @app.get("/")
    async def root(c: Context) -> Response:
        return c.redirect("/app")

    @app.get("/auth")
    async def auth_boundary(c: Context) -> Response:
        html = await renderer.render($htmx_auth_view, {"principal": principal(c)})
        return c.html(html)

    @app.get("/app")
    async def app_index(c: Context) -> Response:
        return await pages.render(
            c,
            page=$htmx_page_view,
            fragment=$htmx_list_view,
            values=await _page_values(c),
        )

    @app.get("/app/stream")
    async def stream_demo(c: Context) -> Response:
        async def tokens() -> AsyncIterator[SSEMessage]:
            for token in (
                "Hayate",
                " keeps",
                " the",
                " stream",
                " safe",
                " and",
                " same-origin.",
            ):
                await asyncio.sleep(0.01)
                yield {"event": "token", "data": {"token": token}}
            yield {"event": "done", "data": "complete"}

        return c.event_stream(tokens(), headers={"x-accel-buffering": "no"})

    @app.post("/app/todos", _csrf_guard)
    async def create(c: Context) -> Response:
        form = await c.req.form_data()
        try:
            title = normalize_title(form.get("title"))
        except InvalidTodoTitle as exc:
            html = await renderer.render($htmx_create_error_view, {"error": str(exc)})
            return with_htmx(
                append_htmx_vary(c.html(html)),
                retarget="#todo-form-errors",
                reswap="innerHTML",
            )

        todo = await create_todo(c, subject(c), title)
        response = await pages.render(
            c,
            page=$htmx_page_view,
            fragment=$htmx_list_view,
            values=await _page_values(c),
            status=201,
        )
        return with_htmx(response, trigger={"todo:created": {"id": todo["id"]}})

    @app.get("/app/todos/:id/edit")
    async def edit(c: Context) -> Response:
        todo = await get_todo(c, subject(c), c.req.param("id") or "")
        if todo is None:
            return c.not_found()
        html = await renderer.render(
            $htmx_edit_view,
            {"error": None, "todo": todo},
        )
        return c.html(html)

    @app.patch("/app/todos/:id", _csrf_guard)
    async def update(c: Context) -> Response:
        todo_id = c.req.param("id") or ""
        todo = await get_todo(c, subject(c), todo_id)
        if todo is None:
            return c.not_found()
        form = await c.req.form_data()
        try:
            title = normalize_title(form.get("title"))
        except InvalidTodoTitle as exc:
            html = await renderer.render(
                $htmx_edit_view,
                {"error": str(exc), "todo": todo},
            )
            return with_htmx(
                c.html(html),
                retarget=f"#todo-{todo['id']}",
                reswap="outerHTML",
            )

        updated = await update_todo(c, subject(c), todo_id, title)
        if updated is None:
            return c.not_found()
        html = await renderer.render(
            $htmx_item_view,
            {"current_filter": _selected_filter(c), "todo": updated},
        )
        return c.html(html)

    @app.patch("/app/todos/:id/toggle", _csrf_guard)
    async def toggle(c: Context) -> Response:
        if await toggle_todo(c, subject(c), c.req.param("id") or "") is None:
            return c.not_found()
        html = await renderer.render($htmx_list_view, await _page_values(c))
        return c.html(html)

    @app.delete("/app/todos/:id", _csrf_guard)
    async def delete(c: Context) -> Response:
        if not await delete_todo(c, subject(c), c.req.param("id") or ""):
            return c.not_found()
        html = await renderer.render($htmx_list_view, await _page_values(c))
        return c.html(html)
