import pytest

from app import app
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
