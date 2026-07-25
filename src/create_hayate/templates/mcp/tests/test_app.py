"""MCP tests call the runtime-agnostic app core directly."""

from app import app

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}


async def test_initializes_and_lists_schema_validated_tool():
    response = await app.request(
        "/mcp",
        method="POST",
        headers={"Accept": MCP_HEADERS["Accept"]},
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
    assert response.status == 200
    assert (await response.json())["result"]["protocolVersion"] == "2025-11-25"

    response = await app.request(
        "/mcp",
        method="POST",
        headers=MCP_HEADERS,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    tool = (await response.json())["result"]["tools"][0]
    assert tool["name"] == "greet"
    assert tool["execution"] == {"taskSupport": "forbidden"}
    assert tool["outputSchema"]["required"] == ["message", "request_id"]


async def test_calls_tool_with_request_context():
    response = await app.request(
        "/mcp",
        method="POST",
        headers={**MCP_HEADERS, "X-Request-ID": "generated-test-1"},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "greet", "arguments": {"name": "Hayate"}},
        },
    )

    assert response.status == 200
    result = (await response.json())["result"]
    assert result["isError"] is False
    assert result["structuredContent"] == {
        "message": "Hello, Hayate!",
        "request_id": "generated-test-1",
    }


async def test_invalid_tool_input_is_model_correctable():
    response = await app.request(
        "/mcp",
        method="POST",
        headers=MCP_HEADERS,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "greet", "arguments": {"name": ""}},
        },
    )

    assert response.status == 200
    result = (await response.json())["result"]
    assert result["isError"] is True
    assert "non-empty" in result["content"][0]["text"]
