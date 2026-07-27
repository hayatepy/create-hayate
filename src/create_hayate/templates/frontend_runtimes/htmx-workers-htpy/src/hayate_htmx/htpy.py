"""Optional typed Python-component renderer backed by :mod:`htpy`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from inspect import isawaitable
from typing import cast

try:
    from htpy import Renderable
except ImportError as exc:  # pragma: no cover - generated optional boundary
    raise ImportError("HtpyRenderer requires htpy; install the generated dependencies") from exc

type HtpyFactory = Callable[
    [Mapping[str, object]],
    Renderable | Awaitable[Renderable],
]
type HtpyView = Renderable | HtpyFactory


class HtpyRenderer:
    """Render reusable htpy objects or context-aware component factories."""

    async def render(
        self,
        view: HtpyView,
        context: Mapping[str, object],
    ) -> str:
        """Render sync or async htpy content without blocking async children."""
        if hasattr(view, "aiter_chunks"):
            renderable = cast(Renderable, view)
        else:
            produced = view(context)
            renderable = await produced if isawaitable(produced) else produced
        return "".join([chunk async for chunk in renderable.aiter_chunks()])


__all__ = ["HtpyFactory", "HtpyRenderer", "HtpyView"]
