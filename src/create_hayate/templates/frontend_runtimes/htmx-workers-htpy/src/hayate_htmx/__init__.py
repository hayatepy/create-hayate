"""Typed htmx integration for Hayate."""

from .jinja import JinjaRenderer, TemplateNotFoundError
from .request import HtmxRequest, RequestType
from .response import (
    HistoryUrl,
    HtmxResponseHeaders,
    LocationValue,
    TriggerValue,
    with_htmx,
)
from .templates import (
    HtmxTemplates,
    Renderer,
    RenderMode,
    ResponseHeaders,
    TemplateRenderer,
    append_htmx_vary,
    select_render_mode,
)

__version__ = "0.2.0"

__all__ = [
    "HistoryUrl",
    "HtmxRequest",
    "HtmxResponseHeaders",
    "HtmxTemplates",
    "JinjaRenderer",
    "LocationValue",
    "RenderMode",
    "Renderer",
    "RequestType",
    "ResponseHeaders",
    "TemplateNotFoundError",
    "TemplateRenderer",
    "TriggerValue",
    "__version__",
    "append_htmx_vary",
    "select_render_mode",
    "with_htmx",
]
