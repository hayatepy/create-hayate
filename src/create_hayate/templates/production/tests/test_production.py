import json
import re
from types import SimpleNamespace

import pytest
from hayate.middleware import current_request_id

from app import app
from feature_observability import request_log
from tests.helpers import AUTH_HEADERS


@pytest.mark.asyncio
async def test_production_headers_and_local_cors_policy():
    response = await app.request(
        "/whoami",
        headers={**AUTH_HEADERS, "Origin": "http://localhost:3000"},
    )
    assert response.status == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("referrer-policy") == "no-referrer"
    assert "default-src 'none'" in response.headers.get("content-security-policy")


@pytest.mark.asyncio
async def test_unlisted_cors_origin_is_not_reflected():
    response = await app.request(
        "/whoami",
        headers={**AUTH_HEADERS, "Origin": "https://attacker.example"},
    )
    assert response.status == 200
    assert response.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_production_health_and_cors_preflight_do_not_require_app_identity(monkeypatch):
    monkeypatch.setattr(
        app,
        "_env",
        SimpleNamespace(
            ENVIRONMENT="production",
            CORS_ORIGINS="https://app.example.com",
        ),
    )

    health = await app.request("/health")
    assert health.status == 200

    preflight = await app.request(
        "/todos",
        method="OPTIONS",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status == 204
    assert preflight.headers.get("access-control-allow-origin") == "https://app.example.com"


@pytest.mark.asyncio
async def test_request_logs_use_final_auth_and_not_found_statuses(
    caplog: pytest.LogCaptureFixture,
):
    request_log.addHandler(caplog.handler)
    try:
        unauthorized = await app.request(
            "/whoami",
            headers={"x-request-id": "generated:unauthorized"},
        )
        missing = await app.request(
            "/missing?secret=must-not-be-logged",
            headers={
                **AUTH_HEADERS,
                "x-request-id": "invalid request id",
            },
        )
    finally:
        request_log.removeHandler(caplog.handler)

    assert unauthorized.status == 401
    assert unauthorized.headers.get("x-request-id") == "generated:unauthorized"
    assert missing.status == 404
    replacement = missing.headers.get("x-request-id")
    assert replacement is not None
    assert replacement != "invalid request id"
    assert re.fullmatch(r"[A-Za-z0-9._:+-]+", replacement)

    events = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == request_log.name
    ]
    assert [(event["path"], event["status"], event["request_id"]) for event in events] == [
        ("/whoami", 401, "generated:unauthorized"),
        ("/missing", 404, replacement),
    ]
    assert all("must-not-be-logged" not in json.dumps(event) for event in events)
    assert current_request_id() is None
