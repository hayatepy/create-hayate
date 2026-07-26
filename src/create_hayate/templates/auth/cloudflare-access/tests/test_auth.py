import time

import pytest

from app import app
from cloudflare_access import (
    AccessConfigurationError,
    AccessDeniedError,
    _normalize_team_domain,
    _validate_claims,
)
from tests.helpers import AUTH_HEADERS


@pytest.mark.asyncio
async def test_protected_routes_require_and_expose_access_identity():
    denied = await app.request("/whoami")
    assert denied.status == 401

    accepted = await app.request("/whoami", headers=AUTH_HEADERS)
    assert accepted.status == 200
    assert await accepted.json() == {
        "subject": "developer@example.com",
        "email": "developer@example.com",
        "credential_type": "cloudflare-access",
    }


@pytest.mark.asyncio
async def test_health_remains_public_for_platform_probes():
    response = await app.request("/health")
    assert response.status == 200


def test_access_claim_validation_is_fail_closed():
    now = int(time.time())
    claims = {
        "aud": ["expected-audience"],
        "iss": "https://team.cloudflareaccess.com",
        "exp": now + 300,
        "iat": now,
        "nbf": now - 1,
        "email": "developer@example.com",
        "type": "app",
        "sub": "stable-access-subject",
    }
    assert (
        _validate_claims(
            claims,
            audience="expected-audience",
            issuer="https://team.cloudflareaccess.com",
            email="developer@example.com",
        )
        == "stable-access-subject"
    )

    invalid = (
        {"aud": ["wrong-audience"]},
        {"iss": "https://attacker.example"},
        {"exp": now - 1},
        {"iat": now + 60},
        {"nbf": now + 60},
        {"email": "attacker@example.com"},
        {"type": "org"},
        {"sub": ""},
    )
    for replacement in invalid:
        with pytest.raises(AccessDeniedError):
            _validate_claims(
                {**claims, **replacement},
                audience="expected-audience",
                issuer="https://team.cloudflareaccess.com",
                email="developer@example.com",
            )


def test_access_team_domain_is_restricted_to_cloudflare_access_https():
    assert (
        _normalize_team_domain("team.cloudflareaccess.com/") == "https://team.cloudflareaccess.com"
    )
    with pytest.raises(AccessConfigurationError):
        _normalize_team_domain("https://attacker.example")
