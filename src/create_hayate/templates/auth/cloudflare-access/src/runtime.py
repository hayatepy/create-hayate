"""Explicit local environment; Workers replaces it with platform bindings."""

from types import SimpleNamespace

LOCAL_ENV = SimpleNamespace(ENVIRONMENT="local")
