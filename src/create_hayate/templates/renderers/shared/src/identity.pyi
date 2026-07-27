"""Type boundary for renderer-focused strict checking."""

from typing import TypedDict

from hayate import Context

class Principal(TypedDict):
    subject: str
    email: str | None
    credential_type: str

def principal(c: Context) -> Principal: ...
def subject(c: Context) -> str: ...
