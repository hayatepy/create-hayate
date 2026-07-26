"""Explicit local defaults; Workers replaces them with platform bindings."""

from types import SimpleNamespace

LOCAL_ENV = SimpleNamespace(
    ENVIRONMENT="local",
    CORS_ORIGINS="http://localhost:3000",
)
