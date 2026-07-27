import html
import re

import pytest

from app import app

OPERATOR = {"Cf-Access-Authenticated-User-Email": "developer@example.com"}
NON_OPERATOR = {"Cf-Access-Authenticated-User-Email": "viewer@example.com"}
MUTATION_HEADERS = {
    **OPERATOR,
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://app.example.com",
}


@pytest.mark.asyncio
async def test_admin_requires_access_and_the_operator_allowlist():
    unauthenticated = await app.request("/admin")
    assert unauthenticated.status == 401

    denied = await app.request("/admin", headers=NON_OPERATOR)
    assert denied.status == 403

    accepted = await app.request("/admin", headers=OPERATOR)
    assert accepted.status == 200
    assert "$project_name Operations" in await accepted.text()


@pytest.mark.asyncio
async def test_admin_crud_is_owner_scoped_origin_checked_and_audited():
    foreign = await app.request(
        "/todos",
        method="POST",
        headers={**NON_OPERATOR, "content-type": "application/json"},
        json={"title": "viewer private record"},
    )
    assert foreign.status == 201

    rejected_origin = await app.request(
        "/admin/todos/create",
        method="POST",
        headers={**MUTATION_HEADERS, "origin": "https://attacker.example"},
        body="title=must-not-exist",
    )
    assert rejected_origin.status == 403

    created = await app.request(
        "/admin/todos/create",
        method="POST",
        headers=MUTATION_HEADERS,
        body="title=%3Cscript%3Ealert%281%29%3C%2Fscript%3E",
    )
    assert created.status == 303
    location = created.headers.get("location")
    assert location is not None
    object_id = location.split("/object/", 1)[1]

    listing = await app.request(
        "/admin/todos?q=alert&o=title",
        headers=OPERATOR,
    )
    html = await listing.text()
    assert listing.status == 200
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "viewer private record" not in html

    updated = await app.request(
        f"/admin/todos/object/{object_id}/edit",
        method="POST",
        headers=MUTATION_HEADERS,
        body="title=shipped&done=on",
    )
    assert updated.status == 303

    history = await app.request(
        f"/admin/todos/object/{object_id}/history",
        headers=OPERATOR,
    )
    history_html = await history.text()
    assert history.status == 200
    assert "resource:add" in history_html
    assert "resource:change" in history_html
    assert "shipped" not in history_html

    deleted = await app.request(
        f"/admin/todos/object/{object_id}/delete",
        method="POST",
        headers=MUTATION_HEADERS,
        body="",
    )
    assert deleted.status == 303


@pytest.mark.asyncio
async def test_admin_saved_view_cursor_and_csv_are_bounded_and_owner_scoped():
    for title in ("Cursor-C", "Cursor-A", "Cursor-B"):
        created = await app.request(
            "/todos",
            method="POST",
            headers={**OPERATOR, "content-type": "application/json"},
            json={"title": title},
        )
        assert created.status == 201

    first = await app.request(
        "/admin/todos?view=title-a-z&q=Cursor-",
        headers=OPERATOR,
    )
    first_html = await first.text()
    assert first.status == 200
    assert "Title A-Z" in first_html
    assert "Cursor-A" in first_html
    assert "Cursor-B" in first_html
    assert "Cursor-C" not in first_html
    next_match = re.search(r'href="([^"]*cursor=[^"]+)"[^>]*>Next</a>', first_html)
    assert next_match is not None

    second = await app.request(html.unescape(next_match.group(1)), headers=OPERATOR)
    second_html = await second.text()
    assert second.status == 200
    assert "Cursor-A" not in second_html
    assert "Cursor-B" not in second_html
    assert "Cursor-C" in second_html

    cross_site = await app.request(
        "/admin/todos/export.csv?view=title-a-z&q=Cursor-",
        headers={**OPERATOR, "sec-fetch-site": "cross-site"},
    )
    assert cross_site.status == 403

    exported = await app.request(
        "/admin/todos/export.csv?view=title-a-z&q=Cursor-",
        headers=OPERATOR,
    )
    csv_body = await exported.text()
    assert exported.status == 200
    assert exported.headers.get("content-disposition") == ('attachment; filename="todos.csv"')
    assert csv_body.startswith("ID,Title,Done\r\n")
    assert "Cursor-A" in csv_body
    assert "Cursor-B" in csv_body
    assert "Cursor-C" in csv_body
    assert "viewer private record" not in csv_body
