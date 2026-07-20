"""Phase 7: forced password change on temporary credentials."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_must_change_password_flow(auth_client: TestClient) -> None:
    # Admin creates a user -> that account is flagged must_change_password.
    created = auth_client.post(
        "/api/v1/users",
        json={"email": "newhire@example.com", "password": "temp-strong-pass-123", "role": "operator"},
    )
    assert created.status_code == 201, created.text

    # Log in as the new user in a fresh client.
    c = TestClient(auth_client.app)
    login = c.post(
        "/api/v1/auth/login",
        json={"email": "newhire@example.com", "password": "temp-strong-pass-123"},
    )
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    c.headers["X-CSRF-Token"] = login.json()["csrf_token"]

    # /me also reports the flag until it's cleared.
    assert c.get("/api/v1/auth/me").json()["must_change_password"] is True

    # Setting a new password clears the flag.
    ch = c.post(
        "/api/v1/auth/change-password",
        json={"current_password": "temp-strong-pass-123", "new_password": "brand-new-pass-456"},
    )
    assert ch.status_code == 200
    assert c.get("/api/v1/auth/me").json()["must_change_password"] is False


def test_admin_reset_reflags_user(auth_client: TestClient) -> None:
    created = auth_client.post(
        "/api/v1/users",
        json={"email": "reset-me@example.com", "password": "initial-strong-pass-1", "role": "operator"},
    ).json()

    # User clears their flag by changing password.
    c = TestClient(auth_client.app)
    login = c.post("/api/v1/auth/login", json={"email": "reset-me@example.com", "password": "initial-strong-pass-1"})
    c.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    c.post("/api/v1/auth/change-password",
           json={"current_password": "initial-strong-pass-1", "new_password": "chosen-strong-pass-2"})
    assert c.get("/api/v1/auth/me").json()["must_change_password"] is False

    # Admin resets the password -> flag comes back on.
    auth_client.post(f"/api/v1/users/{created['id']}/reset-password", json={"password": "admin-reset-pass-3"})
    login2 = c.post("/api/v1/auth/login", json={"email": "reset-me@example.com", "password": "admin-reset-pass-3"})
    assert login2.json()["must_change_password"] is True
