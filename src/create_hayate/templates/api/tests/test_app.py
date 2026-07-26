"""Tests hit the app core directly: no server, no test client, no sockets."""

from app import app


async def test_crud_roundtrip():
    res = await app.request("/todos", method="POST", json={"title": "ship it"})
    assert res.status == 201
    todo = await res.json()
    assert todo["title"] == "ship it"
    assert todo["done"] is False

    res = await app.request(f"/todos/{todo['id']}")
    assert res.status == 200

    res = await app.request("/todos")
    assert any(t["id"] == todo["id"] for t in await res.json())

    res = await app.request(f"/todos/{todo['id']}", method="DELETE")
    assert res.status == 204

    res = await app.request(f"/todos/{todo['id']}")
    assert res.status == 404


async def test_create_requires_string_title():
    res = await app.request("/todos", method="POST", json={"title": 42})
    assert res.status == 400


async def test_internationalized_hostname_uses_uts46():
    res = await app.request("/canonicalize")
    assert await res.json() == {"hostname": "xn--wgv71a119e.example"}
