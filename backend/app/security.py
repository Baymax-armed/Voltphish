"""Cryptographic primitives: password hashing and token generation.

- Passwords: argon2id via argon2-cffi (CLAUDE.md A02 preferred choice).
- Tokens: secrets.token_urlsafe / token_bytes (CSPRNG, CLAUDE.md A02).
- Session lookup tokens are stored HASHED at rest so a DB read alone can't
  resume sessions (defense in depth).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# Sensible argon2id parameters; tune per deployment hardware.
_ph = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    """Constant-time-ish verify. Returns False on any mismatch/format error."""
    try:
        return _ph.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError, Exception):  # noqa: BLE001
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _ph.check_needs_rehash(stored_hash)
    except Exception:  # noqa: BLE001
        return False


# ── Opaque tokens ───────────────────────────────────────────────────────────

def new_session_token() -> str:
    """>=256 bits of entropy (CLAUDE.md A07 requires >=128)."""
    return secrets.token_urlsafe(32)


def new_result_id() -> str:
    """Per-recipient tracking id embedded in emails/links. Unguessable."""
    return secrets.token_urlsafe(16)


def new_api_key() -> str:
    """A REST API key: prefixed for identification, >=256 bits of entropy."""
    return "psk_" + secrets.token_urlsafe(32)


_SHORT_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no ambiguous chars


def new_short_code() -> str:
    """A short click-tracking code for SMS links (keeps the URL small)."""
    return "".join(secrets.choice(_SHORT_ALPHABET) for _ in range(7))


def hash_token(token: str) -> str:
    """SHA-256 of an opaque high-entropy token, for at-rest storage/lookup.

    Safe here (unlike for passwords) because the token itself already has
    >=128 bits of entropy, so it is not brute-forceable.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


# ── Column encryption for secrets at rest (CLAUDE.md A02/A09) ────────────────
# SMTP passwords for Sending Profiles must be stored encrypted, never plaintext.
# We derive a 256-bit key from the app secret via HKDF and use AES-256-GCM.
from base64 import b64decode, b64encode  # noqa: E402

from cryptography.hazmat.primitives import hashes  # noqa: E402
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: E402
from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # noqa: E402

from .config import get_settings  # noqa: E402

_ENC_PREFIX = "gcm:v1:"


def _data_key() -> bytes:
    secret = get_settings().secret_key.encode("utf-8")
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"phishsim-column-encryption")
    return hkdf.derive(secret)


def encrypt_secret(plaintext: str | None) -> str | None:
    if plaintext is None or plaintext == "":
        return plaintext
    nonce = secrets.token_bytes(12)  # 96-bit random nonce per message
    ct = AESGCM(_data_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return _ENC_PREFIX + b64encode(nonce + ct).decode("ascii")


def decrypt_secret(token: str | None) -> str | None:
    if token is None or token == "":
        return token
    if not token.startswith(_ENC_PREFIX):
        # Value predates encryption or is malformed; fail closed.
        raise ValueError("Refusing to use an unencrypted secret value")
    raw = b64decode(token[len(_ENC_PREFIX):])
    nonce, ct = raw[:12], raw[12:]
    return AESGCM(_data_key()).decrypt(nonce, ct, None).decode("utf-8")
