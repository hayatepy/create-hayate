"""Fail-closed Cloudflare Access identity verification."""

import base64
import json
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from hayate import Context, HTTPException, Next

_JWKS_TTL_SECONDS = 3600
_JWKS_CACHE: dict[str, tuple[float, dict[str, dict[str, Any]]]] = {}
_PUBLIC_PATHS = {"/health"}


class AccessDeniedError(Exception):
    """The request does not carry a valid Access identity."""


class AccessConfigurationError(Exception):
    """The production Access trust boundary is incomplete."""


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _jwt_parts(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise AccessDeniedError
    try:
        header = json.loads(_base64url_decode(parts[0]))
        claims = json.loads(_base64url_decode(parts[1]))
        signature = _base64url_decode(parts[2])
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise AccessDeniedError from exc
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise AccessDeniedError
    return header, claims, signature, f"{parts[0]}.{parts[1]}".encode()


def _normalize_team_domain(raw: str) -> str:
    domain = raw.strip().rstrip("/")
    if not domain.startswith("https://"):
        domain = f"https://{domain}"
    parsed = urlparse(domain)
    if parsed.scheme != "https" or parsed.path not in ("", "/") or not parsed.hostname:
        raise AccessConfigurationError
    if not parsed.hostname.endswith(".cloudflareaccess.com"):
        raise AccessConfigurationError
    return f"https://{parsed.hostname}"


def _field(value: object, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


async def _load_jwks(team_domain: str, *, force: bool = False) -> dict[str, dict[str, Any]]:
    cached = _JWKS_CACHE.get(team_domain)
    if not force and cached is not None and time.monotonic() - cached[0] < _JWKS_TTL_SECONDS:
        return cached[1]

    from workers import fetch

    response = await fetch(f"{team_domain}/cdn-cgi/access/certs")
    if not response.ok:
        raise AccessConfigurationError
    payload = await response.json()
    keys = _field(payload, "keys")
    if not isinstance(keys, list):
        raise AccessConfigurationError

    by_id: dict[str, dict[str, Any]] = {}
    for key in keys:
        if isinstance(key, Mapping) and isinstance(key.get("kid"), str):
            by_id[str(key["kid"])] = dict(key)
    if not by_id:
        raise AccessConfigurationError
    _JWKS_CACHE[team_domain] = (time.monotonic(), by_id)
    return by_id


async def _verify_rs256(signing_input: bytes, signature: bytes, jwk: dict[str, Any]) -> bool:
    from js import Object, Uint8Array, crypto
    from pyodide.ffi import to_js

    algorithm = to_js(
        {"name": "RSASSA-PKCS1-v1_5", "hash": "SHA-256"},
        dict_converter=Object.fromEntries,
    )
    key = await crypto.subtle.importKey(
        "jwk",
        to_js(jwk, dict_converter=Object.fromEntries),
        algorithm,
        False,
        to_js(["verify"]),
    )
    return bool(
        await crypto.subtle.verify(
            algorithm,
            key,
            Uint8Array.new(to_js(list(signature))),
            Uint8Array.new(to_js(list(signing_input))),
        )
    )


def _validate_claims(claims: dict[str, Any], *, audience: str, issuer: str, email: str) -> str:
    now = int(time.time())
    token_audience = claims.get("aud")
    audiences = token_audience if isinstance(token_audience, list) else [token_audience]
    subject = claims.get("sub")
    issued_at = claims.get("iat")
    if audience not in audiences or claims.get("iss") != issuer:
        raise AccessDeniedError
    if not isinstance(claims.get("exp"), int | float) or claims["exp"] <= now:
        raise AccessDeniedError
    if not isinstance(issued_at, int | float) or issued_at > now + 30:
        raise AccessDeniedError
    if isinstance(claims.get("nbf"), int | float) and claims["nbf"] > now + 30:
        raise AccessDeniedError
    if not isinstance(claims.get("email"), str) or claims["email"].casefold() != email:
        raise AccessDeniedError
    if claims.get("type") != "app":
        raise AccessDeniedError
    if (
        not isinstance(subject, str)
        or not subject
        or len(subject) > 256
        or any(ord(character) < 33 or ord(character) == 127 for character in subject)
    ):
        raise AccessDeniedError
    return subject


async def _verify_access_token(token: str, *, team_domain: str, audience: str, email: str) -> str:
    header, claims, signature, signing_input = _jwt_parts(token)
    kid = header.get("kid")
    if (
        header.get("alg") != "RS256"
        or header.get("typ") != "JWT"
        or not isinstance(kid, str)
        or not kid
    ):
        raise AccessDeniedError
    keys = await _load_jwks(team_domain)
    jwk = keys.get(kid)
    if jwk is None:
        jwk = (await _load_jwks(team_domain, force=True)).get(kid)
    if jwk is None or not await _verify_rs256(signing_input, signature, jwk):
        raise AccessDeniedError
    return _validate_claims(claims, audience=audience, issuer=team_domain, email=email)


async def access_context(c: Context, next_: Next) -> None:
    if c.req.method == "OPTIONS" or c.req.url.pathname in _PUBLIC_PATHS:
        await next_()
        return
    email_header = c.req.header("cf-access-authenticated-user-email")
    if not email_header or "@" not in email_header:
        raise HTTPException(401, title="Cloudflare Access identity required")
    email = email_header.strip().casefold()

    environment = str(getattr(c.env, "ENVIRONMENT", "")) if c.env is not None else ""
    if environment == "local":
        subject = email
    else:
        if environment != "production" or c.env is None:
            raise HTTPException(500, title="Cloudflare Access is not configured")
        team_domain = getattr(c.env, "ACCESS_TEAM_DOMAIN", None)
        audience = getattr(c.env, "ACCESS_AUD", None)
        token = c.req.header("cf-access-jwt-assertion")
        if not team_domain or not audience:
            raise HTTPException(500, title="Cloudflare Access is not configured")
        if not token:
            raise HTTPException(401, title="Cloudflare Access identity required")
        try:
            issuer = _normalize_team_domain(str(team_domain))
            subject = await _verify_access_token(
                token,
                team_domain=issuer,
                audience=str(audience),
                email=email,
            )
        except AccessDeniedError as exc:
            raise HTTPException(401, title="Cloudflare Access identity required") from exc
        except AccessConfigurationError as exc:
            raise HTTPException(500, title="Cloudflare Access is not configured") from exc

    c.set(
        "principal",
        {
            "subject": subject,
            "email": email,
            "credential_type": "cloudflare-access",
        },
    )
    await next_()
