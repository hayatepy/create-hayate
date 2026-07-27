"""Select and render complete pages or htmx fragments safely."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal, Protocol, TypeVar

from hayate import Context, Headers, Response

from .request import HtmxRequest

type RenderMode = Literal["page", "fragment"]
type ResponseHeaders = Headers | Mapping[str, str] | Iterable[tuple[str, str]] | None

_RendererViewT = TypeVar("_RendererViewT", contravariant=True)
_VARY_FIELDS = (
    "HX-Request",
    "HX-History-Restore-Request",
    "HX-Request-Type",
)


class Renderer(Protocol[_RendererViewT]):
    """Engine-independent asynchronous renderer for one view type."""

    async def render(
        self,
        view: _RendererViewT,
        context: Mapping[str, object],
    ) -> str:
        """Render one view using the supplied values."""
        ...


class TemplateRenderer(Renderer[str], Protocol):
    """Backward-compatible renderer protocol for string template names."""


def select_render_mode(request: HtmxRequest) -> RenderMode:
    """Choose the representation requested from htmx 2 or htmx 4 metadata."""
    if request.request_type == "full":
        return "page"
    if request.request_type == "partial":
        return "fragment"
    if request.history_restore:
        return "page"
    if request.is_htmx:
        return "fragment"
    return "page"


def append_htmx_vary(response: Response) -> Response:
    """Add every request field that can change the rendered representation."""
    existing = response.headers.get("vary")
    if existing is None:
        response.headers.set("vary", ", ".join(_VARY_FIELDS))
        return response

    values = {value.strip().casefold() for value in existing.split(",")}
    if "*" in values:
        return response

    missing = [field for field in _VARY_FIELDS if field.casefold() not in values]
    if missing:
        response.headers.set("vary", f"{existing}, {', '.join(missing)}")
    return response


class HtmxTemplates[ViewT]:
    """Render one route as a complete page or an explicitly named fragment."""

    def __init__(self, renderer: Renderer[ViewT]) -> None:
        self.renderer = renderer

    async def render(
        self,
        context: Context,
        *,
        page: ViewT,
        fragment: ViewT,
        values: Mapping[str, object] | None = None,
        status: int = 200,
        headers: ResponseHeaders = None,
    ) -> Response:
        """Render the representation selected from the request metadata."""
        if isinstance(page, str) and not page:
            raise ValueError("page template name must not be empty")
        if isinstance(fragment, str) and not fragment:
            raise ValueError("fragment template name must not be empty")

        mode = select_render_mode(HtmxRequest.from_context(context))
        view = page if mode == "page" else fragment
        rendered = await self.renderer.render(view, values or {})
        return append_htmx_vary(context.html(rendered, status, headers))
