"""Phase 4: CSV export, user management, change password, scheduling, MIME
import, custom headers."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from .conftest import ADMIN_EMAIL, ADMIN_PASSWORD


def _prereqs(c: TestClient, tag: str) -> dict:
    tpl = c.post(
        "/api/v1/templates",
        json={"name": f"{tag} tpl", "subject": "s", "html": "<a href='{{.URL}}'>x</a>", "text": "x {{.URL}}"},
    ).json()
    prof = c.post(
        "/api/v1/profiles",
        json={"name": f"{tag} prof", "from_address": "it@example.com", "host": "localhost", "port": 1025},
    ).json()
    grp = c.post(
        "/api/v1/groups",
        json={"name": f"{tag} grp", "targets": [{"email": "eve@example.com", "first_name": "Eve"}]},
    ).json()
    return {"tpl": tpl["id"], "prof": prof["id"], "grp": grp["id"]}


# ── CSV export (with formula-injection safety) ──────────────────────────────

def test_results_csv_export_and_injection_safety(auth_client: TestClient) -> None:
    ids = _prereqs(auth_client, "csv")
    # A target whose name starts with '=' would be a spreadsheet formula.
    auth_client.put(
        f"/api/v1/groups/{ids['grp']}",
        json={"name": "csv grp", "targets": [{"email": "mallory@example.com", "first_name": "=SUM(A1)"}]},
    )
    camp = auth_client.post(
        "/api/v1/campaigns",
        json={"name": "csv camp", "template_id": ids["tpl"], "profile_id": ids["prof"],
              "group_id": ids["grp"], "phish_url": "http://testserver"},
    ).json()
    # Launch so per-recipient result rows exist to export.
    auth_client.post(f"/api/v1/campaigns/{camp['id']}/launch", json={"authorized": True})
    for _ in range(50):
        if auth_client.get(f"/api/v1/campaigns/{camp['id']}").json()["stats"]["total"] >= 1:
            break
        time.sleep(0.05)
    r = auth_client.get(f"/api/v1/campaigns/{camp['id']}/results.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    body = r.text
    assert "mallory@example.com" in body
    assert "'=SUM(A1)" in body  # neutralized, not left as a live formula


# ── User management ─────────────────────────────────────────────────────────

def test_user_management_and_last_admin_guard(auth_client: TestClient) -> None:
    created = auth_client.post(
        "/api/v1/users",
        json={"email": "operator1@example.com", "password": "operator-strong-pass", "role": "operator"},
    )
    assert created.status_code == 201, created.text
    uid = created.json()["id"]

    # Admin can't delete themselves or demote the last admin.
    me = auth_client.get("/api/v1/auth/me").json()
    assert auth_client.delete(f"/api/v1/users/{me['id']}").status_code == 400
    assert auth_client.put(f"/api/v1/users/{me['id']}", json={"role": "operator"}).status_code == 400

    # Deleting the operator is fine.
    assert auth_client.delete(f"/api/v1/users/{uid}").status_code == 200


def test_non_admin_cannot_manage_users(client: TestClient) -> None:
    # Create an operator via the admin session first.
    admin = client
    login = admin.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    admin.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    admin.post(
        "/api/v1/users",
        json={"email": "op2@example.com", "password": "operator-strong-pass", "role": "operator"},
    )
    # Now log in AS the operator in a fresh client.
    op = TestClient(admin.app)
    oplogin = op.post("/api/v1/auth/login", json={"email": "op2@example.com", "password": "operator-strong-pass"})
    op.headers["X-CSRF-Token"] = oplogin.json()["csrf_token"]
    assert op.get("/api/v1/users").status_code == 403  # role gate


# ── Change password ─────────────────────────────────────────────────────────

def test_change_password_flow(client: TestClient) -> None:
    c = client
    login = c.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    c.headers["X-CSRF-Token"] = login.json()["csrf_token"]

    # Wrong current password rejected.
    assert c.post("/api/v1/auth/change-password",
                  json={"current_password": "nope", "new_password": "brand-new-strong-pass"}).status_code == 400

    ok = c.post("/api/v1/auth/change-password",
                json={"current_password": ADMIN_PASSWORD, "new_password": "brand-new-strong-pass"})
    assert ok.status_code == 200
    # Change it back so other tests keep working.
    c.post("/api/v1/auth/change-password",
           json={"current_password": "brand-new-strong-pass", "new_password": ADMIN_PASSWORD})


# ── MIME import ─────────────────────────────────────────────────────────────

def test_template_mime_import(auth_client: TestClient) -> None:
    raw = (
        "From: IT Support <it@example.com>\r\n"
        "Subject: Reset your password\r\n"
        'Content-Type: text/html; charset="utf-8"\r\n\r\n'
        "<p>Click <a href='http://x'>here</a></p>\r\n"
    )
    r = auth_client.post("/api/v1/templates/import", json={"raw": raw})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["subject"] == "Reset your password"
    assert data["envelope_sender"] == "it@example.com"
    assert "Click" in data["html"]


# ── Custom headers ──────────────────────────────────────────────────────────

def test_custom_headers_persist_and_reject_crlf(auth_client: TestClient) -> None:
    ok = auth_client.post(
        "/api/v1/profiles",
        json={"name": "hdr prof", "from_address": "it@example.com", "host": "localhost", "port": 1025,
              "headers": [{"key": "X-Mailer", "value": "VoltPhish"}]},
    )
    assert ok.status_code == 201
    assert ok.json()["headers"] == [{"key": "X-Mailer", "value": "VoltPhish"}]

    # CRLF injection in a header is rejected by validation.
    bad = auth_client.post(
        "/api/v1/profiles",
        json={"name": "bad hdr", "from_address": "it@example.com", "host": "localhost", "port": 1025,
              "headers": [{"key": "X-Evil", "value": "a\r\nBcc: victim@example.com"}]},
    )
    assert bad.status_code == 422


# ── Scheduling ──────────────────────────────────────────────────────────────

def test_future_launch_is_scheduled(auth_client: TestClient) -> None:
    ids = _prereqs(auth_client, "sched")
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    camp = auth_client.post(
        "/api/v1/campaigns",
        json={"name": "sched camp", "template_id": ids["tpl"], "profile_id": ids["prof"],
              "group_id": ids["grp"], "phish_url": "http://testserver", "launch_at": future},
    )
    assert camp.status_code == 201, camp.text
    assert camp.json()["status"] == "scheduled"


def test_send_by_before_launch_rejected(auth_client: TestClient) -> None:
    ids = _prereqs(auth_client, "sched2")
    now = datetime.now(timezone.utc)
    camp = auth_client.post(
        "/api/v1/campaigns",
        json={"name": "bad window", "template_id": ids["tpl"], "profile_id": ids["prof"],
              "group_id": ids["grp"], "phish_url": "http://testserver",
              "launch_at": (now + timedelta(hours=2)).isoformat(),
              "send_by_at": (now + timedelta(hours=1)).isoformat()},
    )
    assert camp.status_code == 422
