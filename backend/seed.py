"""Create the initial admin user from env, idempotently.

Usage:
    VOLTPHISH_BOOTSTRAP_ADMIN_EMAIL=you@example.com \
    VOLTPHISH_BOOTSTRAP_ADMIN_PASSWORD='<strong password>' \
    python seed.py

Fails closed if no password is provided (CLAUDE.md §0.3) — we never create an
account with a default/empty password.
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import User, UserRole
from app.security import hash_password

MIN_PASSWORD_LEN = 12


def main() -> int:
    settings = get_settings()
    email = settings.bootstrap_admin_email.strip().lower()
    password = settings.bootstrap_admin_password

    if not password or len(password) < MIN_PASSWORD_LEN:
        print(
            f"Refusing to seed: set VOLTPHISH_BOOTSTRAP_ADMIN_PASSWORD to a value "
            f"of at least {MIN_PASSWORD_LEN} characters.",
            file=sys.stderr,
        )
        return 1

    init_db()
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            print(f"Admin '{email}' already exists (id={existing.id}); nothing to do.")
            return 0
        user = User(email=email, password_hash=hash_password(password), role=UserRole.admin)
        db.add(user)
        db.commit()
        print(f"Created admin '{email}' (id={user.id}). Rotate this password after first login.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
