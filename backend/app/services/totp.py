"""TOTP (RFC 6238) helpers for admin two-factor auth.

Wraps the vetted `pyotp` library (CLAUDE.md 0.2 — never hand-roll crypto). The
per-user secret is generated here, stored AES-256-GCM encrypted at rest by the
caller (security.encrypt_secret), and never logged. `verify` uses a ±1 step
window to tolerate mild clock drift.
"""
from __future__ import annotations

import base64
import hmac
import io
import time

import pyotp
import segno

_ISSUER = "VoltPhish"


def new_secret() -> str:
    """Return a fresh base32 TOTP secret (160-bit)."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account: str) -> str:
    """otpauth:// URI for authenticator apps (Google Authenticator, Authy, …)."""
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=_ISSUER)


_INTERVAL = 30


def verify(secret: str, code: str) -> bool:
    """True if `code` is valid for `secret` now (±1 step for clock drift)."""
    return matched_step(secret, code) is not None


def matched_step(secret: str, code: str) -> int | None:
    """Return the TOTP time-step the code matches (±1 for drift), or None. The
    step lets the caller reject replays (a code accepted at step N must not be
    accepted again — RFC 6238)."""
    if not secret or not code:
        return None
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return None
    try:
        totp = pyotp.TOTP(secret)
        now = int(time.time())
        for offset in (-1, 0, 1):
            ts = now + offset * _INTERVAL
            if hmac.compare_digest(totp.at(ts), code):
                return ts // _INTERVAL
    except Exception:
        return None
    return None


def qr_data_uri(uri: str) -> str:
    """Render the provisioning URI as an inline PNG data URI for the enroll UI."""
    buff = io.BytesIO()
    segno.make(uri, error="m").save(buff, kind="png", scale=5, border=2)
    b64 = base64.b64encode(buff.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
