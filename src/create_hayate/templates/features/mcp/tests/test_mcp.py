import pytest

from app import app
from tests.helpers import AUTH_HEADERS

MCP_HEADERS = {
    **AUTH_HEADERS,
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


@pytest.mark.asyncio
async def test_mcp_2025_11_25_uses_request_identity_and_application_storage():
    initialized = await app.request(
        "/mcp",
        method="POST",
        headers=MCP_HEADERS,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "generated-test", "version": "1.0.0"},
            },
        },
    )
    assert initialized.status == 200
    assert (await initialized.json())["result"]["protocolVersion"] == "2025-11-25"

    created = await app.request(
        "$api_prefix/todos",
        method="POST",
        headers=AUTH_HEADERS,
        json={"title": "visible through MCP"},
    )
    assert created.status == 201

    called = await app.request(
        "/mcp",
        method="POST",
        headers={**MCP_HEADERS, "MCP-Protocol-Version": "2025-11-25"},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "list_todos", "arguments": {}},
        },
    )
    assert called.status == 200
    result = (await called.json())["result"]["structuredContent"]
    assert result["subject"]
    assert any(todo["title"] == "visible through MCP" for todo in result["todos"])
