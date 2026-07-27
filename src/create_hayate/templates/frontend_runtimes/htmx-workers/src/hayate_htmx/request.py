"""Typed access to htmx request headers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from hayate import Context, HayateRequest, Request

type RequestType = Literal["full", "partial"]


def _is_true(value: str | None) -> bool:
    return value is not None and value.casefold() == "true"


@dataclass(frozen=True, slots=True)
class HtmxRequest:
    """An immutable typed view over htmx metadata on a Hayate request."""

    request: Request | HayateRequest

    @classmethod
    def from_context(cls, context: Context) -> HtmxRequest:
        """Build a view from the request carried by a Hayate context."""
        return cls(context.req)

    def header(self, name: str) -> str | None:
        """Read a raw request header through Hayate's Fetch-normalized headers."""
        return self.request.headers.get(name)

    @property
    def is_htmx(self) -> bool:
        """Whether htmx initiated the request (`HX-Request: true`)."""
        return _is_true(self.header("hx-request"))

    @property
    def boosted(self) -> bool:
        """Whether an `hx-boost` anchor or form initiated the request."""
        return _is_true(self.header("hx-boosted"))

    @property
    def current_url(self) -> str | None:
        """The browser URL reported by htmx."""
        return self.header("hx-current-url")

    @property
    def history_restore(self) -> bool:
        """Whether htmx 2 is restoring a history entry after a cache miss."""
        return _is_true(self.header("hx-history-restore-request"))

    @property
    def target(self) -> str | None:
        """The current htmx target, in the version-specific wire format."""
        return self.header("hx-target")

    @property
    def trigger(self) -> str | None:
        """The htmx 2 triggering element identifier."""
        return self.header("hx-trigger")

    @property
    def trigger_name(self) -> str | None:
        """The htmx 2 triggering element name."""
        return self.header("hx-trigger-name")

    @property
    def request_type(self) -> RequestType | None:
        """The htmx 4 request type, rejecting unknown future values."""
        value = self.header("hx-request-type")
        if value not in ("full", "partial"):
            return None
        return cast(RequestType, value)

    @property
    def source(self) -> str | None:
        """The htmx 4 source element in its `tag#id` wire format."""
        return self.header("hx-source")
