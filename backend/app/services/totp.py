"""TOTP (RFC 6238) helpers for admin two-factor auth.

Wraps the vetted `pyotp` library (CLAUDE.md 0.2 — never hand-roll crypto). The
per-user secret is generated here, stored AES-256-GCM encrypted at rest by the
caller (security.encrypt_secret), and never logged. `verify` uses a ±1 step
window to tolerate mild clock drift.
"""
from __future__ import annotations

import base64
import io

import pyotp
import segno

_ISSUER = "VoltPhish"


def new_secret() -> str:
    """Return a fresh base32 TOTP secret (160-bit)."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account: str) -> str:
    """otpauth:// URI for authenticator apps (Google Authenticator, Authy, …)."""
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=_ISSUER)


def verify(secret: str, code: str) -> bool:
    """True if `code` is valid for `secret` now (±1 step for clock drift)."""
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:
        return False


def qr_data_uri(uri: str) -> str:
    """Render the provisioning URI as an inline PNG data URI for the enroll UI."""
    buff = io.BytesIO()
    segno.make(uri, error="m").save(buff, kind="png", scale=5, border=2)
    b64 = base64.b64encode(buff.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
