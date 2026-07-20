"""First-run admin bootstrap (Gophish-style).

On startup, if there are no users, create an admin account:
  - password from PHISHSIM_BOOTSTRAP_ADMIN_PASSWORD if set, else a random one
    that is printed ONCE to the logs. This makes `docker compose up` usable
    immediately after clone with no manual seed step.

The generated password is shown only at creation time and never stored in
plaintext (argon2id hash only).
"""
from __future__ import annotations

import logging
import secrets

from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .models import SendingProfile, User, UserRole
from .security import hash_password

log = logging.getLogger("phishsim.bootstrap")


def ensure_admin() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        has_user = db.execute(select(User.id).limit(1)).first() is not None
        if has_user:
            return

        email = settings.bootstrap_admin_email.strip().lower()
        password = settings.bootstrap_admin_password
        generated = False
        if not password or len(password) < 12:
            password = secrets.token_urlsafe(18)
            generated = True

        db.add(
            User(
                email=email,
                password_hash=hash_password(password),
                role=UserRole.admin,
                # A generated password is temporary — force a change on first login.
                must_change_password=generated,
            )
        )
        db.commit()

        banner = "=" * 68
        if generated:
            log.warning(
                "\n%s\n  VoltPhish first-run admin created\n"
                "    email:    %s\n    password: %s\n"
                "  ^ Shown ONCE. Log in and change it. Set "
                "PHISHSIM_BOOTSTRAP_ADMIN_PASSWORD to choose your own.\n%s",
                banner, email, password, banner,
            )
        else:
            log.info("First-run admin created for %s (password from env).", email)
    finally:
        db.close()


def ensure_dev_smtp_profile() -> None:
    """If PHISHSIM_DEV_SMTP_HOST is set (e.g. the bundled Mailpit) and no sending
    profiles exist yet, create a ready-to-use one so email works out of the box."""
    settings = get_settings()
    if not settings.dev_smtp_host:
        return
    db = SessionLocal()
    try:
        if db.execute(select(SendingProfile.id).limit(1)).first() is not None:
            return
        db.add(
            SendingProfile(
                name="Local Mailpit (test)",
                from_address="phishsim@example.com",
                kind="smtp",
                host=settings.dev_smtp_host,
                port=settings.dev_smtp_port,
                use_starttls=False,
                use_ssl=False,
                ignore_cert_errors=True,
            )
        )
        db.commit()
        log.info(
            "Created default 'Local Mailpit (test)' SMTP profile (%s:%s). "
            "Emails you send will appear in the Mailpit inbox.",
            settings.dev_smtp_host, settings.dev_smtp_port,
        )
    finally:
        db.close()
