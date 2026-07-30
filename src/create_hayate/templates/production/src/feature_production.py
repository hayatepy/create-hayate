"""Production middleware with platform-native configuration boundaries."""

from collections.abc import Mapping
from typing import Any

from hayate import Context, Hayate, HTTPException, Next
from hayate.middleware import body_limit, cors, secure_headers

from release_metadata import release_metadata

_PLATFORM_PUBLIC_PATHS = {"/health"}


def _allowed_origin(c: Context, request_origin: str) -> str | None:
    raw = getattr(c.env, "CORS_ORIGINS", "") if c.env is not None else ""
    allowed = {origin.strip() for origin in str(raw).split(",") if origin.strip()}
    return request_origin if request_origin in allowed else None


def _field(value: object, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


async def _platform_controls(c: Context, next_: Next) -> None:
    if c.req.method == "OPTIONS" or c.req.url.pathname in _PLATFORM_PUBLIC_PATHS:
        await next_()
        return
    environment = str(getattr(c.env, "ENVIRONMENT", "")) if c.env is not None else ""
    if environment == "local":
        await next_()
        return
    if environment != "production" or c.env is None:
        raise HTTPException(503, title="Production environment is not configured")
    app_version, worker_version = release_metadata(c.env)
    if app_version is None:
        raise HTTPException(503, title="Application version is not configured")
    if worker_version is None:
        raise HTTPException(503, title="Worker version metadata is not configured")
    if getattr(c.env, "DB", None) is None:
        raise HTTPException(503, title="D1 binding is not configured")
    limiter = getattr(c.env, "API_RATE_LIMITER", None)
    if limiter is None:
        raise HTTPException(503, title="Rate-limit binding is not configured")
    active = c.get("principal")
    key = active.get("subject") if isinstance(active, dict) else None
    if not isinstance(key, str) or not key:
        raise HTTPException(401, title="Authenticated identity required")
    try:
        result = await limiter.limit({"key": key})
    except Exception as exc:
        raise HTTPException(503, title="Rate-limit binding is unavailable") from exc
    if _field(result, "success") is not True:
        raise HTTPException(429, title="Too Many Requests", headers={"retry-after": "60"})
    await next_()


def register(app: Hayate) -> None:
    app.use(
        secure_headers(
            content_security_policy=(
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
            permissions_policy="camera=(), microphone=(), geolocation=()",
        )
    )
    app.use(
        cors(
            origin_resolver=_allowed_origin,
            allow_headers=("content-type", "mcp-protocol-version"),
            expose_headers=("x-app-version", "x-request-id", "x-worker-version"),
            max_age=600,
        )
    )
    app.use(body_limit(max_size=1_048_576))
    app.use(_platform_controls)
