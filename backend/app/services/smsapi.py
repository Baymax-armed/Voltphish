"""Send SMS (smishing) via a gateway provider over HTTPS.

Providers:
  console  - writes the message to an outbox file (no real send). Always free;
             use it to test the whole flow like Mailpit does for email.
  textbelt - dead-simple free tier (key "textbelt" = 1 free SMS/day).
  twilio   - account SID + auth token + from number.
  generic  - a custom HTTP gateway (URL + JSON body template) so any provider
             (MSG91, Fast2SMS, Gupshup, Vonage, ...) can be plugged in.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from ..config import get_settings
from ..models import SmsProfile
from ..security import decrypt_secret

log = logging.getLogger("phishsim.smsapi")
settings = get_settings()
_TIMEOUT = 20.0

PROVIDERS = {
    "console": ("Console (test — writes to outbox, no real send)", False),
    "textbelt": ("TextBelt (free tier)", True),
    "twilio": ("Twilio", True),
    "generic": ("Generic HTTP gateway (MSG91 / Fast2SMS / etc.)", True),
}


class SmsError(Exception):
    """SMS send/verify failure, human-readable."""


def _outbox() -> Path:
    p = Path(settings.mail_outbox).parent / "sms-outbox"
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _send_console(profile: SmsProfile, to: str, body: str) -> None:
    from email.utils import make_msgid

    path = _outbox() / f"{to.replace('+','').replace('/','_')}-{make_msgid()[1:10]}.txt"
    path.write_text(f"To: {to}\nFrom: {profile.from_number or 'PhishSim'}\n\n{body}\n", encoding="utf-8")
    log.info("console SMS written to %s", path)


async def _send_textbelt(profile: SmsProfile, to: str, body: str) -> None:
    key = decrypt_secret(profile.secret_encrypted) or "textbelt"  # "textbelt" = free 1/day
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post("https://textbelt.com/text", data={"phone": to, "message": body, "key": key})
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not data.get("success"):
            raise SmsError(f"TextBelt: {data.get('error') or r.text[:200]}")


async def _send_twilio(profile: SmsProfile, to: str, body: str) -> None:
    sid = profile.account
    token = decrypt_secret(profile.secret_encrypted)
    if not sid or not token or not profile.from_number:
        raise SmsError("Twilio needs Account SID, Auth Token, and a From number.")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={"To": to, "From": profile.from_number, "Body": body},
        )
        if r.status_code >= 400:
            raise SmsError(f"Twilio HTTP {r.status_code}: {r.text[:200]}")


async def _send_generic(profile: SmsProfile, to: str, body: str) -> None:
    """config JSON: {"url","method","headers":{},"body":{...with {phone}/{message}}, "json":true}."""
    try:
        cfg = json.loads(profile.config or "{}")
    except ValueError:
        raise SmsError("Generic provider config is not valid JSON.")
    url = cfg.get("url")
    if not url:
        raise SmsError("Generic provider needs a 'url' in its config.")
    secret = decrypt_secret(profile.secret_encrypted) or ""

    def sub(v):
        if isinstance(v, str):
            return v.replace("{phone}", to).replace("{message}", body).replace("{secret}", secret).replace("{from}", profile.from_number or "")
        if isinstance(v, dict):
            return {k: sub(x) for k, x in v.items()}
        return v

    method = (cfg.get("method") or "POST").upper()
    headers = sub(cfg.get("headers") or {})
    payload = sub(cfg.get("body") or {})
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        kwargs = {"headers": headers}
        if cfg.get("json"):
            kwargs["json"] = payload
        else:
            kwargs["data"] = payload
        r = await c.request(method, url, **kwargs)
        if r.status_code >= 400:
            raise SmsError(f"Gateway HTTP {r.status_code}: {r.text[:200]}")


_SENDERS = {
    "console": _send_console, "textbelt": _send_textbelt,
    "twilio": _send_twilio, "generic": _send_generic,
}


async def send_sms(profile: SmsProfile, to: str, body: str) -> None:
    sender = _SENDERS.get(profile.provider)
    if sender is None:
        raise SmsError(f"Unknown SMS provider '{profile.provider}'.")
    if not to:
        raise SmsError("Recipient has no phone number.")
    await sender(profile, to, body)


async def verify_sms(profile: SmsProfile) -> None:
    """Light validation. For console, always OK. For real providers, check that
    the required credentials are present (a full send is the true test)."""
    p = profile.provider
    if p == "console":
        return
    if p == "textbelt":
        return  # key optional (free), real send validates
    if p == "twilio":
        if not (profile.account and decrypt_secret(profile.secret_encrypted) and profile.from_number):
            raise SmsError("Twilio needs Account SID, Auth Token, and From number.")
        # Validate credentials via a cheap authenticated GET.
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{profile.account}.json",
                auth=(profile.account, decrypt_secret(profile.secret_encrypted) or ""),
            )
            if r.status_code in (401, 403):
                raise SmsError("Twilio credentials were rejected.")
            if r.status_code >= 400:
                raise SmsError(f"Twilio HTTP {r.status_code}")
        return
    if p == "generic":
        try:
            cfg = json.loads(profile.config or "{}")
        except ValueError:
            raise SmsError("Generic config is not valid JSON.")
        if not cfg.get("url"):
            raise SmsError("Generic provider needs a 'url'.")
        return
    raise SmsError(f"Unknown provider '{p}'.")
