"""Request identity shared by HTTP and MCP features."""

from typing import TypedDict

from hayate import Context


class Principal(TypedDict):
    subject: str
    email: str | None
    credential_type: str


_ANONYMOUS = Principal(
    subject="anonymous",
    email=None,
    credential_type="none",
)


def principal(c: Context) -> Principal:
    active = c.get("principal")
    return active if isinstance(active, dict) else _ANONYMOUS


def subject(c: Context) -> str:
    return principal(c)["subject"]
