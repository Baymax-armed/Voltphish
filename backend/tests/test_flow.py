"""End-to-end happy path plus abuse cases (CLAUDE.md §10)."""
from __future__ import annotations

from fastapi.testclient import TestClient


# ── Abuse / auth cases ───────────────────────────────────────────────────────

def test_unauthenticated_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/templates").status_code == 401


def test_login_wrong_password_is_generic(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_unknown_user_same_error(client: TestClient) -> None:
    # No user enumeration: same message/status as a wrong password.
    r = client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_template_requires_body(auth_client: TestClient) -> None:
    r = auth_client.post("/api/v1/templates", json={"name": "empty", "subject": "hi"})
    assert r.status_code == 422  # schema rejects missing html+text


def test_mutation_without_csrf_is_forbidden(client: TestClient) -> None:
    # Authenticate (sets the session cookie) but do NOT send X-CSRF-Token.
    login = client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "correct-horse-battery-staple"}
    )
    assert login.status_code == 200
    resp = client.post("/api/v1/templates", json={"name": "x", "subject": "s", "text": "t"})
    assert resp.status_code == 403
    # A GET (safe method) still works with just the cookie.
    assert client.get("/api/v1/templates").status_code == 200


def test_security_headers_present(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in r.headers


# ── Full flow: template -> profile -> group -> campaign -> launch -> track ────

def test_full_campaign_flow(auth_client: TestClient) -> None:
    # 1. Template with personalization + an explicit tracking link.
    tpl = auth_client.post(
        "/api/v1/templates",
        json={
            "name": "IT password reset",
            "subject": "Action needed, {{.FirstName}}",
            "html": '<p>Hi {{.FirstName}}, <a href="{{.URL}}">verify your account</a>.</p>',
            "text": "Hi {{.FirstName}}, verify: {{.URL}}",
        },
    ).json()

    # 2. Sending profile (console backend ignores SMTP details, but they validate).
    prof = auth_client.post(
        "/api/v1/profiles",
        json={
            "name": "Lab SMTP",
            "from_address": "it-support@example.com",
            "host": "localhost",
            "port": 1025,
            "password": "super-secret",
        },
    ).json()
    assert prof["has_password"] is True
    assert "password" not in prof  # secret never echoed back

    # 3. Group of targets.
    grp = auth_client.post(
        "/api/v1/groups",
        json={
            "name": "Finance",
            "targets": [
                {"email": "alice@example.com", "first_name": "Alice"},
                {"email": "bob@example.com", "first_name": "Bob"},
            ],
        },
    ).json()
    assert len(grp["targets"]) == 2

    # 4. Campaign.
    camp = auth_client.post(
        "/api/v1/campaigns",
        json={
            "name": "Q3 Finance Test",
            "template_id": tpl["id"],
            "profile_id": prof["id"],
            "group_id": grp["id"],
            "phish_url": "http://testserver",
            "redirect_url": "http://testserver/awareness",
        },
    ).json()
    campaign_id = camp["id"]

    # 5. Launch. Background send runs against the console backend.
    launched = auth_client.post(f"/api/v1/campaigns/{campaign_id}/launch")
    assert launched.status_code == 200, launched.text

    # Poll until both emails are sent (background task).
    detail = _wait_for(auth_client, campaign_id, lambda s: s["sent"] == 2)
    assert detail["stats"]["sent"] == 2

    # 6. Simulate a recipient opening and clicking, using their real rid.
    rid = detail["results"][0]["rid"]

    assert auth_client.get(f"/t/{rid}.png").status_code == 200          # open pixel
    click = auth_client.get(f"/c/{rid}", follow_redirects=False)
    assert click.status_code == 302                                    # click -> redirect

    # 7. Stats reflect the open + click for that one recipient.
    detail2 = auth_client.get(f"/api/v1/campaigns/{campaign_id}").json()
    assert detail2["stats"]["opened"] >= 1
    assert detail2["stats"]["clicked"] >= 1

    # 8. Landing submission records submitted_data but NOT the password.
    sub = auth_client.post(
        f"/p/{rid}", data={"username": "alice@example.com", "password": "hunter2"},
        follow_redirects=False,
    )
    assert sub.status_code == 303
    events = auth_client.get(f"/api/v1/campaigns/{campaign_id}/events").json()
    dump = str(events)
    assert "hunter2" not in dump          # password never stored anywhere
    assert any(e["type"] == "submitted_data" for e in events)


def test_invalid_rid_is_benign(client: TestClient) -> None:
    # Unknown rid: pixel still returned, click still redirects, nothing recorded.
    assert client.get("/t/not-a-real-rid.png").status_code == 200
    assert client.get("/c/not-a-real-rid", follow_redirects=False).status_code == 302


# ── helpers ──────────────────────────────────────────────────────────────────

def _wait_for(client: TestClient, campaign_id: int, pred, tries: int = 50):
    import time

    last = None
    for _ in range(tries):
        last = client.get(f"/api/v1/campaigns/{campaign_id}").json()
        if pred(last["stats"]):
            return last
        time.sleep(0.1)
    return last
