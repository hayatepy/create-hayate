"""Bounded application and Cloudflare Worker release metadata."""

import re
from collections.abc import Mapping

_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+-]{1,128}$$")


def _field(value: object, name: str) -> object | None:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _safe_value(value: object | None) -> str | None:
    if not isinstance(value, str) or _VALUE_PATTERN.fullmatch(value) is None:
        return None
    return value


def release_metadata(env: object | None) -> tuple[str | None, str | None]:
    """Return the semantic application version and active Worker version ID."""
    raw_app_version = _field(env, "APP_VERSION") if env is not None else None
    app_version = _safe_value(raw_app_version)
    worker = _field(env, "CF_VERSION_METADATA") if env is not None else None
    worker_version = _safe_value(_field(worker, "id")) if worker is not None else None
    return app_version, worker_version
