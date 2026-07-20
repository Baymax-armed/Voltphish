"""Phase 8: Email-API sending profiles (send over HTTPS, no SMTP ports)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_api_profile_hides_key(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/v1/profiles",
        json={
            "name": "Brevo API", "from_address": "it@example.com",
            "kind": "api", "api_provider": "brevo", "api_key": "xkeysib-secret",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "api"
    assert body["api_provider"] == "brevo"
    assert body["has_api_key"] is True
    assert "api_key" not in body
    assert "xkeysib-secret" not in str(body)


def test_api_profile_requires_key_on_create(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/v1/profiles",
        json={"name": "NoKey", "from_address": "it@example.com", "kind": "api", "api_provider": "sendgrid"},
    )
    assert r.status_code == 422  # api_key required


def test_mailgun_requires_domain(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/v1/profiles",
        json={"name": "MG", "from_address": "it@example.com", "kind": "api",
              "api_provider": "mailgun", "api_key": "key-abc"},
    )
    assert r.status_code == 422  # mailgun needs api_domain


def test_smtp_profile_still_requires_host(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/v1/profiles",
        json={"name": "NoHost", "from_address": "it@example.com", "kind": "smtp"},
    )
    assert r.status_code == 422  # host required for smtp


def test_verify_api_profile_rejects_bad_key(auth_client: TestClient) -> None:
    prof = auth_client.post(
        "/api/v1/profiles",
        json={"name": "BadBrevo", "from_address": "it@example.com", "kind": "api",
              "api_provider": "brevo", "api_key": "definitely-not-a-real-key"},
    ).json()
    r = auth_client.post(f"/api/v1/profiles/{prof['id']}/verify")
    # Real call to Brevo with a bogus key -> rejected (needs network; if offline,
    # still a 400 with a connection error, which is also acceptable).
    assert r.status_code == 400
    assert "API check failed" in r.json()["detail"]
