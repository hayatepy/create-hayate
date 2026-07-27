from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlencode

import pytest

from app import app
from tests.helpers import AUTH_HEADERS

FORM_HEADERS = {
    **AUTH_HEADERS,
    "content-type": "application/x-www-form-urlencoded",
    "origin": "http://localhost",
    "HX-Request": "true",
}


@pytest.mark.asyncio
async def test_page_fragment_crud_validation_and_shared_api():
    page = await app.request("/app", headers=AUTH_HEADERS)
    assert page.status == 200
    assert (await page.text()).startswith("<!doctype html>")
    assert page.headers.get("content-security-policy") is not None
    assert page.headers.get("cache-control") == "private, no-store"

    fragment = await app.request(
        "/app",
        headers={**AUTH_HEADERS, "HX-Request": "true"},
    )
    assert (await fragment.text()).startswith('<section id="todo-list"')
    assert fragment.headers.get("vary") == (
        "HX-Request, HX-History-Restore-Request, HX-Request-Type"
    )

    invalid = await app.request(
        "/app/todos",
        method="POST",
        headers=FORM_HEADERS,
        body=urlencode({"title": "   "}),
    )
    assert invalid.status == 200
    assert invalid.headers.get("hx-retarget") == "#todo-form-errors"
    assert 'role="alert"' in await invalid.text()

    unsafe_title = '<img src=x onerror="alert(1)">'
    created = await app.request(
        "/app/todos",
        method="POST",
        headers=FORM_HEADERS,
        body=urlencode({"title": unsafe_title}),
    )
    created_html = await created.text()
    assert created.status == 201
    assert "&lt;img" in created_html
    assert "<img" not in created_html

    listed = await app.request("/api/todos", headers=AUTH_HEADERS)
    todos = await listed.json()
    todo = next(item for item in todos if item["title"] == unsafe_title)
    todo_id = todo["id"]

    edit = await app.request(
        f"/app/todos/{todo_id}/edit",
        headers={**AUTH_HEADERS, "HX-Request": "true"},
    )
    assert 'value="&lt;img' in await edit.text()

    updated = await app.request(
        f"/app/todos/{todo_id}",
        method="PATCH",
        headers=FORM_HEADERS,
        body=urlencode({"title": "Ship the generated profile"}),
    )
    assert "Ship the generated profile" in await updated.text()

    toggled = await app.request(
        f"/app/todos/{todo_id}/toggle?filter=done",
        method="PATCH",
        headers=FORM_HEADERS,
        body="",
    )
    toggled_html = await toggled.text()
    assert 'data-filter="done"' in toggled_html
    assert "Ship the generated profile" in toggled_html

    cross_origin = await app.request(
        "/app/todos",
        method="POST",
        headers={**FORM_HEADERS, "origin": "https://attacker.example"},
        body=urlencode({"title": "stolen"}),
    )
    assert cross_origin.status == 403

    deleted = await app.request(
        f"/app/todos/{todo_id}",
        method="DELETE",
        headers=FORM_HEADERS,
    )
    assert "Ship the generated profile" not in await deleted.text()


@pytest.mark.asyncio
async def test_history_identity_assets_and_stream():
    restored = await app.request(
        "/app",
        headers={
            **AUTH_HEADERS,
            "HX-Request": "true",
            "HX-History-Restore-Request": "true",
        },
    )
    assert (await restored.text()).startswith("<!doctype html>")

    identity = await app.request("/auth", headers=AUTH_HEADERS)
    assert identity.status == 200
    assert "Request identity" in await identity.text()

    asset = await app.request(
        "/assets/vendor/htmx-2.0.10.min.js",
        headers=AUTH_HEADERS,
    )
    assert asset.status == 200
    assert asset.headers.get("cache-control") == "public, max-age=31536000, immutable"
    assert hashlib.sha256(await asset.bytes()).hexdigest() == (
        "71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de"
    )

    stream = await app.request("/app/stream", headers=AUTH_HEADERS)
    body = await stream.text()
    assert stream.headers.get("content-type") == "text/event-stream"
    assert 'event: token\ndata: {"token":"Hayate"}' in body
    assert "event: done\ndata: complete" in body


def test_vendored_asset_matches_the_profile_manifest():
    root = Path(__file__).resolve().parents[1]
    asset = root / "public/assets/vendor/htmx-2.0.10.min.js"
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == (
        "71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de"
    )
