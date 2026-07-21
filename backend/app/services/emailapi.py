"""Send email over HTTPS through provider APIs (no SMTP ports needed).

Each provider needs only an API key (Mailgun also needs a domain). This is the
recommended path when outbound SMTP (25/465/587) is firewalled, since everything
goes over port 443.

Supported: SendGrid, Brevo (Sendinblue), Resend, Mailgun, Postmark.
"""
from __future__ import annotations

import base64
import logging

import httpx

from ..models import SendingProfile
from ..security import decrypt_secret

log = logging.getLogger("voltphish.emailapi")

_TIMEOUT = 20.0

# name -> (label, needs_domain, signup_url)
PROVIDERS = {
    "sendgrid": ("SendGrid", False, "https://sendgrid.com"),
    "brevo": ("Brevo (Sendinblue)", False, "https://www.brevo.com"),
    "resend": ("Resend", False, "https://resend.com"),
    "mailgun": ("Mailgun", True, "https://www.mailgun.com"),
    "postmark": ("Postmark", False, "https://postmarkapp.com"),
}


class EmailApiError(Exception):
    """Provider send/verify failure, with a human-readable reason."""


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _raise_for(resp: httpx.Response, provider: str) -> None:
    if resp.status_code >= 400:
        body = (resp.text or "")[:300]
        raise EmailApiError(f"{provider} returned HTTP {resp.status_code}: {body}")


# ── Senders ─────────────────────────────────────────────────────────────────

async def _send_sendgrid(p: SendingProfile, key: str, msg) -> None:  # noqa: ANN001
    content = []
    if msg.text:
        content.append({"type": "text/plain", "value": msg.text})
    if msg.html:
        content.append({"type": "text/html", "value": msg.html})
    if not content:
        content = [{"type": "text/plain", "value": " "}]
    payload = {
        "personalizations": [{"to": [{"email": msg.to_address}]}],
        "from": {"email": msg.from_address},
        "subject": msg.subject,
        "content": content,
    }
    if msg.extra_headers:
        payload["headers"] = {k: v for k, v in msg.extra_headers}
    if msg.attachments:
        payload["attachments"] = [
            {"content": _b64(raw), "filename": name, "type": ctype, "disposition": "attachment"}
            for name, ctype, raw in msg.attachments
        ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post("https://api.sendgrid.com/v3/mail/send",
                         headers={"Authorization": f"Bearer {key}"}, json=payload)
        _raise_for(r, "SendGrid")


async def _send_brevo(p: SendingProfile, key: str, msg) -> None:  # noqa: ANN001
    payload = {
        "sender": {"email": msg.from_address},
        "to": [{"email": msg.to_address}],
        "subject": msg.subject,
    }
    if msg.html:
        payload["htmlContent"] = msg.html
    if msg.text:
        payload["textContent"] = msg.text
    if not msg.html and not msg.text:
        payload["textContent"] = " "
    if msg.extra_headers:
        payload["headers"] = {k: v for k, v in msg.extra_headers}
    if msg.attachments:
        payload["attachment"] = [{"content": _b64(raw), "name": name} for name, _, raw in msg.attachments]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post("https://api.brevo.com/v3/smtp/email",
                         headers={"api-key": key, "accept": "application/json"}, json=payload)
        _raise_for(r, "Brevo")


async def _send_resend(p: SendingProfile, key: str, msg) -> None:  # noqa: ANN001
    payload = {"from": msg.from_address, "to": [msg.to_address], "subject": msg.subject}
    if msg.html:
        payload["html"] = msg.html
    if msg.text:
        payload["text"] = msg.text
    if msg.extra_headers:
        payload["headers"] = {k: v for k, v in msg.extra_headers}
    if msg.attachments:
        payload["attachments"] = [{"filename": name, "content": _b64(raw)} for name, _, raw in msg.attachments]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post("https://api.resend.com/emails",
                         headers={"Authorization": f"Bearer {key}"}, json=payload)
        _raise_for(r, "Resend")


async def _send_mailgun(p: SendingProfile, key: str, msg) -> None:  # noqa: ANN001
    if not p.api_domain:
        raise EmailApiError("Mailgun requires a sending domain.")
    data = {"from": msg.from_address, "to": msg.to_address, "subject": msg.subject}
    if msg.text:
        data["text"] = msg.text
    if msg.html:
        data["html"] = msg.html
    for k, v in msg.extra_headers:
        data[f"h:{k}"] = v
    files = [("attachment", (name, raw, ctype)) for name, ctype, raw in msg.attachments]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(f"https://api.mailgun.net/v3/{p.api_domain}/messages",
                         auth=("api", key), data=data, files=files or None)
        _raise_for(r, "Mailgun")


async def _send_postmark(p: SendingProfile, key: str, msg) -> None:  # noqa: ANN001
    payload = {
        "From": msg.from_address, "To": msg.to_address, "Subject": msg.subject,
        "MessageStream": "outbound",
    }
    if msg.html:
        payload["HtmlBody"] = msg.html
    if msg.text:
        payload["TextBody"] = msg.text
    if msg.extra_headers:
        payload["Headers"] = [{"Name": k, "Value": v} for k, v in msg.extra_headers]
    if msg.attachments:
        payload["Attachments"] = [
            {"Name": name, "Content": _b64(raw), "ContentType": ctype}
            for name, ctype, raw in msg.attachments
        ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post("https://api.postmarkapp.com/email",
                         headers={"X-Postmark-Server-Token": key, "Accept": "application/json"}, json=payload)
        _raise_for(r, "Postmark")


_SENDERS = {
    "sendgrid": _send_sendgrid, "brevo": _send_brevo, "resend": _send_resend,
    "mailgun": _send_mailgun, "postmark": _send_postmark,
}


# ── Verifiers (cheap authenticated GET to validate the key) ─────────────────

async def _verify_generic(url: str, headers: dict, provider: str, auth=None) -> None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.get(url, headers=headers, auth=auth)
        if r.status_code in (401, 403):
            raise EmailApiError(f"{provider}: the API key was rejected (unauthorized).")
        if r.status_code >= 400:
            raise EmailApiError(f"{provider} returned HTTP {r.status_code}: {(r.text or '')[:200]}")


async def _verify(profile: SendingProfile, key: str) -> None:
    prov = profile.api_provider
    if prov == "sendgrid":
        await _verify_generic("https://api.sendgrid.com/v3/scopes", {"Authorization": f"Bearer {key}"}, "SendGrid")
    elif prov == "brevo":
        await _verify_generic("https://api.brevo.com/v3/account", {"api-key": key}, "Brevo")
    elif prov == "resend":
        await _verify_generic("https://api.resend.com/domains", {"Authorization": f"Bearer {key}"}, "Resend")
    elif prov == "mailgun":
        await _verify_generic("https://api.mailgun.net/v3/domains", {}, "Mailgun", auth=("api", key))
    elif prov == "postmark":
        await _verify_generic("https://api.postmarkapp.com/server", {"X-Postmark-Server-Token": key}, "Postmark")
    else:
        raise EmailApiError(f"Unknown provider '{prov}'.")


# ── Public API ──────────────────────────────────────────────────────────────

async def send_via_api(msg, profile: SendingProfile) -> None:  # noqa: ANN001
    key = decrypt_secret(profile.api_key_encrypted)
    if not key:
        raise EmailApiError("No API key set on this profile.")
    sender = _SENDERS.get(profile.api_provider or "")
    if sender is None:
        raise EmailApiError(f"Unknown provider '{profile.api_provider}'.")
    await sender(profile, key, msg)


async def verify_api(profile: SendingProfile) -> None:
    key = decrypt_secret(profile.api_key_encrypted)
    if not key:
        raise EmailApiError("No API key set on this profile.")
    await _verify(profile, key)
