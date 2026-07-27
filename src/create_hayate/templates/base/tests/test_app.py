import json

import pytest
from hayate.middleware import current_request_id

from app import app
from feature_observability import request_log
from tests.helpers import AUTH_HEADERS


@pytest.mark.asyncio
async def test_health_and_identity():
    health = await app.request("$api_prefix/health")
    assert health.status == 200
    assert await health.json() == {"status": "ok"}

    identity = await app.request("$api_prefix/whoami", headers=AUTH_HEADERS)
    assert identity.status == 200
    principal = await identity.json()
    assert isinstance(principal["subject"], str)


@pytest.mark.asyncio
async def test_todo_crud_is_scoped_to_the_request_identity():
    created = await app.request(
        "$api_prefix/todos",
        method="POST",
        headers=AUTH_HEADERS,
        json={"title": "ship the production path"},
    )
    assert created.status == 201
    todo = await created.json()

    listed = await app.request("$api_prefix/todos", headers=AUTH_HEADERS)
    assert listed.status == 200
    assert todo in await listed.json()

    invalid_path = await app.request("$api_prefix/todos/not-a-uuid", headers=AUTH_HEADERS)
    assert invalid_path.status == 400
    assert (await invalid_path.json())["title"] == "Validation failed"

    shown = await app.request(f"$api_prefix/todos/{todo['id']}", headers=AUTH_HEADERS)
    assert shown.status == 200
    assert await shown.json() == todo

    updated = await app.request(
        f"$api_prefix/todos/{todo['id']}",
        method="PATCH",
        headers=AUTH_HEADERS,
        json={"title": "ship the complete production path"},
    )
    assert updated.status == 200
    assert (await updated.json())["title"] == "ship the complete production path"

    deleted = await app.request(
        f"$api_prefix/todos/{todo['id']}",
        method="DELETE",
        headers=AUTH_HEADERS,
    )
    assert deleted.status == 204

    missing = await app.request(f"$api_prefix/todos/{todo['id']}", headers=AUTH_HEADERS)
    assert missing.status == 404


@pytest.mark.asyncio
async def test_malformed_json_is_a_validation_problem():
    response = await app.request(
        "$api_prefix/todos",
        method="POST",
        headers={**AUTH_HEADERS, "content-type": "application/json"},
        body="not json",
    )
    assert response.status == 400
    assert (await response.json())["title"] == "Validation failed"


@pytest.mark.asyncio
async def test_request_logs_are_correlated_structured_and_query_free(
    caplog: pytest.LogCaptureFixture,
):
    request_log.addHandler(caplog.handler)
    try:
        response = await app.request(
            "$api_prefix/health?access_token=must-not-be-logged",
            headers={"x-request-id": "generated:request-42"},
        )
    finally:
        request_log.removeHandler(caplog.handler)

    assert response.status == 200
    assert response.headers.get("x-request-id") == "generated:request-42"
    record = next(record for record in caplog.records if record.name == request_log.name)
    event = json.loads(record.getMessage())
    duration_ms = event.pop("duration_ms")
    assert event == {
        "event": "http_request",
        "method": "GET",
        "path": "$api_prefix/health",
        "status": 200,
        "request_id": "generated:request-42",
    }
    assert isinstance(duration_ms, float)
    assert duration_ms >= 0
    assert record.__dict__["request_id"] == "generated:request-42"
    assert "must-not-be-logged" not in record.getMessage()
    assert current_request_id() is None
