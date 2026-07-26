"""OpenAPI annotations are a no-op unless the openapi feature is installed."""

from collections.abc import Callable
from typing import Any


def describe[F: Callable[..., Any]](**_metadata: Any) -> Callable[[F], F]:
    def decorate(handler: F) -> F:
        return handler

    return decorate
