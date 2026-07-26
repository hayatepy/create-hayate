"""MCP 2025-11-25 tools over the same identity and storage boundaries."""

import json

from hayate import Hayate
from hayate_mcp import WorkerMcpMount, WorkerMcpServer, get_request_context

from identity import principal, subject
from storage import list_todos

server = WorkerMcpServer(
    "$project_name",
    title="$project_name MCP",
    version="0.1.0",
    instructions="Use list_todos to inspect the current caller's todo collection.",
)


@server.tool(
    name="list_todos",
    title="List todos",
    description="List todos owned by the authenticated request identity.",
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "todos": {"type": "array"},
        },
        "required": ["subject", "todos"],
        "additionalProperties": False,
    },
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    execution={"taskSupport": "forbidden"},
)
async def list_todos_tool(_arguments: dict[str, object]) -> dict[str, object]:
    context = get_request_context()
    if context is None:
        raise RuntimeError("list_todos must run through the registered MCP mount")
    active = principal(context)
    structured: dict[str, object] = {
        "subject": active["subject"],
        "todos": await list_todos(context, subject(context)),
    }
    return {
        "content": [{"type": "text", "text": json.dumps(structured)}],
        "structuredContent": structured,
        "isError": False,
    }


def register(app: Hayate) -> None:
    WorkerMcpMount(server, path="/mcp").register(app)
