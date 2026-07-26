from types import SimpleNamespace

import pytest

from app import app
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
