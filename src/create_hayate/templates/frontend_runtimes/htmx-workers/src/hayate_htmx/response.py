"""Apply htmx response control headers to ordinary Hayate responses."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from hayate import Response

type HistoryUrl = str | Literal[False]
type LocationValue = str | Mapping[str, object]
type TriggerValue = str | Sequence[str] | Mapping[str, object]


def _json_header(value: Mapping[str, object]) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _location_header(value: LocationValue) -> str:
    return value if isinstance(value, str) else _json_header(value)


def _history_header(value: HistoryUrl) -> str:
    if value is False:
        return "false"
    if not isinstance(value, str):
        raise TypeError("htmx history URL must be a string or False")
    return value


def _trigger_header(value: TriggerValue) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return _json_header(value)
    events = tuple(value)
    if not events:
        raise ValueError("htmx trigger sequence must not be empty")
    if not all(isinstance(event, str) and event for event in events):
        raise TypeError("htmx trigger names must be non-empty strings")
    return ", ".join(events)


@dataclass(frozen=True, slots=True, kw_only=True)
class HtmxResponseHeaders:
    """Declarative htmx response controls that can be applied to a response."""

    location: LocationValue | None = None
    push_url: HistoryUrl | None = None
    redirect: str | None = None
    refresh: bool | None = None
    replace_url: HistoryUrl | None = None
    reswap: str | None = None
    retarget: str | None = None
    reselect: str | None = None
    trigger: TriggerValue | None = None

    def apply(self, response: Response) -> Response:
        """Mutate the supplied response headers and return that same response."""
        if self.location is not None:
            response.headers.set("hx-location", _location_header(self.location))
        if self.push_url is not None:
            response.headers.set("hx-push-url", _history_header(self.push_url))
        if self.redirect is not None:
            response.headers.set("hx-redirect", self.redirect)
        if self.refresh is not None:
            response.headers.set("hx-refresh", "true" if self.refresh else "false")
        if self.replace_url is not None:
            response.headers.set("hx-replace-url", _history_header(self.replace_url))
        if self.reswap is not None:
            response.headers.set("hx-reswap", self.reswap)
        if self.retarget is not None:
            response.headers.set("hx-retarget", self.retarget)
        if self.reselect is not None:
            response.headers.set("hx-reselect", self.reselect)
        if self.trigger is not None:
            response.headers.set("hx-trigger", _trigger_header(self.trigger))
        return response


def with_htmx(
    response: Response,
    *,
    location: LocationValue | None = None,
    push_url: HistoryUrl | None = None,
    redirect: str | None = None,
    refresh: bool | None = None,
    replace_url: HistoryUrl | None = None,
    reswap: str | None = None,
    retarget: str | None = None,
    reselect: str | None = None,
    trigger: TriggerValue | None = None,
) -> Response:
    """Apply htmx response controls without wrapping the Hayate response."""
    return HtmxResponseHeaders(
        location=location,
        push_url=push_url,
        redirect=redirect,
        refresh=refresh,
        replace_url=replace_url,
        reswap=reswap,
        retarget=retarget,
        reselect=reselect,
        trigger=trigger,
    ).apply(response)
