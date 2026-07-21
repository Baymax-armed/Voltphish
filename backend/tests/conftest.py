"""Test fixtures. Uses an isolated temp SQLite DB and the console mail backend
so no real email is ever sent and no global state is touched."""
from __future__ import annotations

import os
import tempfile

import pytest

# Configure the app via env BEFORE importing it (settings are cached).
_TMP = tempfile.mkdtemp(prefix="voltphish-test-")
os.environ.update(
    VOLTPHISH_ENV="development",
    VOLTPHISH_SECRET_KEY="test-secret-key-at-least-16-chars-long-xxxxxx",
    VOLTPHISH_DATABASE_URL=f"sqlite+pysqlite:///{_TMP}/test.db".replace("\\", "/"),
    VOLTPHISH_MAIL_BACKEND="console",
    VOLTPHISH_MAIL_OUTBOX=f"{_TMP}/outbox",
    VOLTPHISH_PHISH_BASE_URL="http://testserver",
    VOLTPHISH_COOKIE_SECURE="false",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.security import hash_password  # noqa: E402

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(scope="session", autouse=True)
def _db():
    init_db()
    db = SessionLocal()
    try:
        db.add(User(email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD), role=UserRole.admin))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def client():
    # Enter the app lifespan (starts the queue workers + scheduler) so durable
    # jobs actually get processed during tests.
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    resp = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    # Echo the per-session CSRF token on every subsequent request (as the SPA does).
    client.headers["X-CSRF-Token"] = resp.json()["csrf_token"]
    return client
