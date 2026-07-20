"""Email delivery.

Two backends:
  console -> writes each message as a .eml file to the outbox (no network send).
             Lets you exercise the full flow with zero real email. Default.
  smtp    -> delivers via a Sending Profile's SMTP server over STARTTLS/SSL.

TLS is verified by default; ignore_cert_errors must be explicitly enabled on the
profile and is intended only for lab hosts with self-signed certs (CLAUDE.md A02).
Every network call has a bounded timeout (CLAUDE.md §8).
"""
from __future__ import annotations

import json
import logging
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

import aiosmtplib

from ..config import get_settings
from ..models import SendingProfile
from ..security import decrypt_secret

log = logging.getLogger("phishsim.mailer")
settings = get_settings()

SMTP_TIMEOUT_SECONDS = 30


@dataclass
class OutgoingEmail:
    to_address: str
    from_address: str            # display From: header (may be spoofed)
    subject: str
    html: str | None
    text: str | None
    envelope_from: str | None = None  # SMTP MAIL FROM (SPF); None => use from_address
    extra_headers: list[tuple[str, str]] = field(default_factory=list)
    # (filename, content_type, raw_bytes)
    attachments: list[tuple[str, str, bytes]] = field(default_factory=list)


_RESERVED_HEADERS = {"from", "to", "subject", "message-id", "content-type", "mime-version"}


def _build_message(msg: OutgoingEmail) -> EmailMessage:
    email = EmailMessage()
    email["From"] = msg.from_address
    email["To"] = msg.to_address
    email["Subject"] = msg.subject
    email["Message-ID"] = make_msgid()
    for key, value in msg.extra_headers:
        # Don't let custom headers clobber the ones we control; CRLF already
        # rejected at the schema layer.
        if key.lower() not in _RESERVED_HEADERS:
            email[key] = value
    # Always provide a text part; add HTML as an alternative if present.
    email.set_content(msg.text or "This message requires an HTML-capable client.")
    if msg.html:
        email.add_alternative(msg.html, subtype="html")
    for filename, content_type, raw in msg.attachments:
        maintype, _, subtype = content_type.partition("/")
        email.add_attachment(
            raw,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=filename,
        )
    return email


def _tls_context(ignore_cert_errors: bool) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if ignore_cert_errors:
        # SECURITY: disables cert verification. Lab/self-signed use only.
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def _send_console(msg: OutgoingEmail) -> None:
    outbox = Path(settings.mail_outbox)
    outbox.mkdir(parents=True, exist_ok=True)
    safe = msg.to_address.replace("@", "_at_").replace("/", "_").replace("\\", "_")
    # Path is confined to the outbox dir; filename derived from a validated email.
    path = outbox / f"{safe}-{make_msgid(domain='phishsim')[1:12]}.eml"
    path.write_bytes(bytes(_build_message(msg)))
    log.info("console mail written to %s", path)


async def _send_smtp(msg: OutgoingEmail, profile: SendingProfile) -> None:
    password = decrypt_secret(profile.password_encrypted)
    tls = _tls_context(profile.ignore_cert_errors)
    # sender = the envelope MAIL FROM (SPF/Return-Path), which can differ from
    # the From: header in the message (that's how a spoofed display From still
    # passes SPF via an authorized envelope address).
    await aiosmtplib.send(
        _build_message(msg),
        sender=msg.envelope_from or msg.from_address,
        recipients=[msg.to_address],
        hostname=profile.host,
        port=profile.port,
        username=profile.username or None,
        password=password or None,
        use_tls=profile.use_ssl,          # implicit TLS (e.g. port 465)
        start_tls=profile.use_starttls,   # STARTTLS (e.g. port 587)
        tls_context=tls,
        timeout=SMTP_TIMEOUT_SECONDS,
    )


class SmtpVerifyError(Exception):
    """Raised when an SMTP connection/authentication check fails, with a
    human-readable reason (safe to show the operator, not the recipient)."""


def friendly_smtp_error(exc: Exception) -> str:
    """Turn an aiosmtplib/ssl/socket error into a concise, actionable message."""
    name = type(exc).__name__
    text = str(exc).strip() or name
    hints = {
        "SMTPAuthenticationError": "authentication failed — check the username/password.",
        "SMTPConnectError": "could not connect — check the host and port.",
        "SMTPConnectTimeoutError": "connection timed out — check host/port and firewall.",
        "SMTPServerDisconnected": "server disconnected — TLS settings may be wrong (try toggling STARTTLS/SSL).",
        "SMTPNotSupportedError": "the server rejected a requested feature (e.g. STARTTLS not supported).",
        "SMTPSenderRefused": "the server refused the From address.",
    }
    # Self-signed / untrusted certificate is common on internal SMTP relays.
    if "certificate" in text.lower() or "CERTIFICATE_VERIFY_FAILED" in text or name in (
        "SSLCertVerificationError", "SSLError"
    ):
        return f"{text} (the server's TLS certificate isn't trusted — enable 'Ignore TLS certificate errors' if this is an internal/self-signed server)."
    hint = hints.get(name)
    return f"{text} ({hint})" if hint else f"{name}: {text}"


async def verify_smtp(profile: SendingProfile) -> None:
    """Actually connect to the profile's SMTP server, negotiate TLS, and (if
    credentials are set) authenticate — then disconnect WITHOUT sending mail.
    Raises SmtpVerifyError with a clear reason on any failure."""
    password = decrypt_secret(profile.password_encrypted)
    tls = _tls_context(profile.ignore_cert_errors)
    client = aiosmtplib.SMTP(
        hostname=profile.host,
        port=profile.port,
        use_tls=profile.use_ssl,
        start_tls=profile.use_starttls if not profile.use_ssl else False,
        tls_context=tls,
        timeout=SMTP_TIMEOUT_SECONDS,
    )
    try:
        await client.connect()
        if profile.username:
            await client.login(profile.username, password or "")
    except Exception as exc:  # noqa: BLE001
        raise SmtpVerifyError(friendly_smtp_error(exc)) from exc
    finally:
        try:
            await client.quit()
        except Exception:  # noqa: BLE001
            pass


def profile_headers(profile: SendingProfile) -> list[tuple[str, str]]:
    """Custom SMTP headers stored on the profile (JSON) as (key, value) tuples."""
    if not profile.headers:
        return []
    try:
        return [(h["key"], h["value"]) for h in json.loads(profile.headers)]
    except (ValueError, KeyError, TypeError):
        return []


async def send_email(msg: OutgoingEmail, profile: SendingProfile, *, allow_console: bool = True) -> None:
    """Deliver one message. Raises on failure; caller records the error.

    Delivery path by profile kind:
      - api  -> send over HTTPS via the provider's API (ignores console mode).
      - smtp -> real SMTP, unless allow_console and the global backend is
                'console' (dev), in which case it's written to the outbox.
    """
    if profile.kind == "api":
        from .emailapi import send_via_api  # local import avoids a cycle
        await send_via_api(msg, profile)
    elif allow_console and settings.mail_backend.value == "console":
        await _send_console(msg)
    else:
        await _send_smtp(msg, profile)
