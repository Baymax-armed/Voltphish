"""Phase 5: durable queue, webhooks (SSRF + HMAC), REST API keys."""
from __future__ import annotations

import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from app.services.ssrf import SsrfError, validate_url
from app.services.handlers import webhook_signature


# ── SSRF guard (pure unit, no network for IP literals) ──────────────────────

@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/hook",
        "http://169.254.169.254/latest/meta-data",  # cloud metadata
        "http://192.168.1.10/x",
        "http://10.0.0.5/x",
        "http://[::1]/x",
        "ftp://8.8.8.8/x",  # scheme not allowed
    ],
)
def test_ssrf_blocks_internal(url: str) -> None:
    with pytest.raises(SsrfError):
        validate_url(url)


def test_ssrf_allows_public_ip() -> None:
    validate_url("https://93.184.216.34/hook")  # public IP literal, no DNS


def test_webhook_signature_matches_hmac() -> None:
    body = b'{"a":1}'
    expected = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert webhook_signature("s3cret", body) == expected


# ── Webhook CRUD + SSRF at save + secret hidden ─────────────────────────────

def test_webhook_rejects_internal_url(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/v1/webhooks",
        json={"name": "bad", "url": "http://127.0.0.1:9000/hook", "secret": "x"},
    )
    assert r.status_code == 400


def test_webhook_crud_hides_secret(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/v1/webhooks",
        json={"name": "ext", "url": "https://93.184.216.34/hook", "secret": "topsecret", "is_active": False},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["has_secret"] is True
    assert "secret" not in body
    assert "topsecret" not in str(body)


# ── REST API keys: bearer auth works and is CSRF-exempt ─────────────────────

def test_api_key_bearer_auth(auth_client: TestClient) -> None:
    created = auth_client.post("/api/v1/apikeys", json={"name": "ci"})
    assert created.status_code == 201, created.text
    key = created.json()["key"]
    assert key.startswith("psk_")
    # Listing shows only the prefix, never the full key.
    listed = auth_client.get("/api/v1/apikeys").json()
    assert all("key" not in k for k in listed)
    assert any(key.startswith(k["prefix"]) for k in listed)

    # Use the key from a FRESH client (no session cookie, no CSRF header).
    api = TestClient(auth_client.app)
    h = {"Authorization": f"Bearer {key}"}
    assert api.get("/api/v1/templates", headers=h).status_code == 200
    # A mutating call works with the bearer key and NO CSRF token.
    made = api.post(
        "/api/v1/templates",
        headers=h,
        json={"name": "via-api-key", "subject": "s", "text": "t"},
    )
    assert made.status_code == 201, made.text

    # Revoke, then the key stops working.
    kid = created.json()["id"]
    assert auth_client.delete(f"/api/v1/apikeys/{kid}").status_code == 200
    assert api.get("/api/v1/templates", headers=h).status_code == 401


def test_bad_bearer_is_unauthorized(client: TestClient) -> None:
    r = client.get("/api/v1/templates", headers={"Authorization": "Bearer psk_not_a_real_key"})
    assert r.status_code == 401
