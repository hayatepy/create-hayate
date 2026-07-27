"""Runtime contracts; the OpenAPI feature adds schema projection."""

from collections.abc import Callable
from typing import Any, Literal

from hayate import Middleware, validator

type ValidationTarget = Literal["json", "form", "query", "param", "header", "cookie"]


def describe[F: Callable[..., Any]](**_metadata: Any) -> Callable[[F], F]:
    def decorate(handler: F) -> F:
        return handler

    return decorate


def validated(
    target: ValidationTarget,
    _schema: Any,
    **_metadata: Any,
) -> Middleware:
    """Store normalized input without requiring an OpenAPI dependency."""
    return validator(target, lambda data: data)
