"""Queue job handlers. Imported by queue.start_workers() so the @register
decorators run before the workers start consuming."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging

import httpx

from ..config import get_settings
from ..database import SessionLocal
from ..models import (
    Campaign,
    CampaignStatus,
    EventType,
    Result,
    ResultStatus,
    Webhook,
    utcnow,
)
from ..security import decrypt_secret
from .events import record_event
from .mailer import OutgoingEmail, friendly_smtp_error, profile_headers, send_email
from .queue import register
from .renderer import RenderContext, render_html, render_subject, render_text
from .ssrf import SsrfError, validate_url

log = logging.getLogger("phishsim.handlers")
settings = get_settings()

_TERMINAL_DELIVERED = {
    ResultStatus.sent, ResultStatus.opened, ResultStatus.clicked,
    ResultStatus.submitted, ResultStatus.reported,
}


def build_attachments(template) -> list[tuple[str, str, bytes]]:  # noqa: ANN001
    """Decode a template's stored attachments into (name, content_type, bytes)."""
    out: list[tuple[str, str, bytes]] = []
    for att in getattr(template, "attachments", []) or []:
        try:
            raw = base64.b64decode(att.content_b64)
        except (binascii.Error, ValueError):
            continue
        out.append((att.filename, att.content_type, raw))
    return out


@register("send_email")
async def handle_send_email(payload: dict) -> None:
    result_id = int(payload["result_id"])
    db = SessionLocal()
    try:
        result = db.get(Result, result_id)
        if result is None:
            return
        campaign = db.get(Campaign, result.campaign_id)
        if campaign is None:
            return
        # Idempotency guard: if already delivered (e.g. an orphaned job was
        # requeued after a crash), don't send again.
        if result.status in _TERMINAL_DELIVERED:
            return

        template, profile = campaign.template, campaign.profile
        ctx = RenderContext(
            first_name=result.first_name or "",
            last_name=result.last_name or "",
            email=result.email,
            position=result.position or "",
            rid=result.rid,
            phish_url=campaign.phish_url,
        )
        subject = render_subject(template.subject, ctx)
        html = render_html(template.html, ctx) if template.html else None
        text = render_text(template.text, ctx) if template.text else None
        from_addr = template.envelope_sender or profile.from_address

        result.status = ResultStatus.sending
        db.commit()

        try:
            await send_email(
                OutgoingEmail(
                    to_address=result.email, from_address=from_addr, subject=subject,
                    html=html, text=text, envelope_from=profile.envelope_sender,
                    extra_headers=profile_headers(profile),
                    attachments=build_attachments(template),
                ),
                profile,
            )
        except Exception as exc:  # noqa: BLE001
            # SMTP failures are terminal for this recipient (recorded, not retried).
            reason = friendly_smtp_error(exc)
            log.warning("send failed campaign=%s rid=%s: %s", campaign.id, result.rid, reason)
            result.send_error = reason[:500]
            record_event(db, campaign_id=campaign.id, rid=result.rid,
                         type=EventType.email_error, details={"error": reason[:200]})
            db.commit()
            _maybe_complete(db, campaign.id)
            return

        result.sent_at = utcnow()
        record_event(db, campaign_id=campaign.id, rid=result.rid, type=EventType.email_sent)
        db.commit()
        _maybe_complete(db, campaign.id)
    finally:
        db.close()


@register("send_sms")
async def handle_send_sms(payload: dict) -> None:
    from ..models import SmsProfile
    from .renderer import render_sms
    from .smsapi import SmsError, send_sms

    result_id = int(payload["result_id"])
    db = SessionLocal()
    try:
        result = db.get(Result, result_id)
        if result is None:
            return
        campaign = db.get(Campaign, result.campaign_id)
        if campaign is None:
            return
        if result.status in _TERMINAL_DELIVERED:
            return
        profile = db.get(SmsProfile, campaign.sms_profile_id) if campaign.sms_profile_id else None
        if profile is None:
            result.status = ResultStatus.error
            result.send_error = "No SMS profile configured"
            record_event(db, campaign_id=campaign.id, rid=result.rid, type=EventType.email_error,
                         details={"error": "no sms profile"})
            db.commit()
            _maybe_complete(db, campaign.id)
            return

        ctx = RenderContext(
            first_name=result.first_name or "", last_name=result.last_name or "",
            email=result.email, position=result.position or "", rid=result.rid,
            phish_url=campaign.phish_url, short_code=result.short_code or "",
        )
        body = render_sms(campaign.template.text or "", ctx)

        result.status = ResultStatus.sending
        db.commit()
        try:
            await send_sms(profile, result.phone or "", body)
        except (SmsError, Exception) as exc:  # noqa: BLE001
            reason = f"{type(exc).__name__}: {exc}" if not isinstance(exc, SmsError) else str(exc)
            log.warning("sms send failed campaign=%s rid=%s: %s", campaign.id, result.rid, reason)
            result.send_error = reason[:500]
            record_event(db, campaign_id=campaign.id, rid=result.rid,
                         type=EventType.email_error, details={"error": reason[:200]})
            db.commit()
            _maybe_complete(db, campaign.id)
            return

        result.sent_at = utcnow()
        record_event(db, campaign_id=campaign.id, rid=result.rid, type=EventType.email_sent)
        db.commit()
        _maybe_complete(db, campaign.id)
    finally:
        db.close()


def _maybe_complete(db, campaign_id: int) -> None:
    """Mark the campaign completed once no recipients remain to be sent."""
    remaining = (
        db.query(Result)
        .filter(
            Result.campaign_id == campaign_id,
            Result.status.in_([ResultStatus.scheduled, ResultStatus.sending]),
        )
        .count()
    )
    if remaining:
        return
    campaign = db.get(Campaign, campaign_id)
    if campaign and campaign.status is not CampaignStatus.completed:
        campaign.status = CampaignStatus.completed
        campaign.completed_at = utcnow()
        db.commit()


def webhook_signature(secret: str, body: bytes) -> str:
    """HMAC-SHA256 of the exact request body, hex-encoded. Receivers verify with
    the same secret to authenticate the delivery."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@register("deliver_webhook")
async def handle_deliver_webhook(payload: dict) -> None:
    webhook_id = int(payload["webhook_id"])
    event = payload["event"]

    db = SessionLocal()
    try:
        webhook = db.get(Webhook, webhook_id)
        if webhook is None or not webhook.is_active:
            return
        url = webhook.url
        fmt = getattr(webhook, "format", "generic") or "generic"
        secret = decrypt_secret(webhook.secret_encrypted) or ""
        # Enrich the human-readable chat message with campaign name + recipient.
        campaign_name = email = None
        if fmt in ("slack", "teams"):
            camp = db.get(Campaign, int(event.get("campaign_id") or 0))
            campaign_name = camp.name if camp else None
            rid = event.get("rid")
            if rid:
                res = db.query(Result).filter(Result.rid == rid).one_or_none()
                email = res.email if res else None
    finally:
        db.close()

    # SSRF guard before any network call (CLAUDE.md A10).
    try:
        validate_url(url)
    except SsrfError as exc:
        log.warning("webhook %s blocked by SSRF guard: %s", webhook_id, exc)
        return  # don't retry a structurally-unsafe URL

    body, headers = build_webhook_body(fmt, secret, event, campaign_name, email)

    # follow_redirects=False so a 3xx can't bounce us to an internal host.
    async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
        resp = await client.post(url, content=body, headers=headers)
        if resp.status_code >= 400:
            # Raise so the queue retries with backoff.
            raise RuntimeError(f"webhook returned HTTP {resp.status_code}")


_EVENT_LABELS = {
    "email_sent": ("📧", "was sent the email"),
    "email_opened": ("👀", "opened the email"),
    "clicked_link": ("⚠️", "clicked the phishing link"),
    "submitted_data": ("🚨", "SUBMITTED credentials"),
    "reported": ("✅", "reported the phishing email"),
}


def _chat_message(event: dict, campaign_name: str | None, email: str | None) -> str:
    """Human-readable one-liner for Slack/Teams."""
    if event.get("test"):
        return "✅ VoltPhish test notification — this webhook is connected and working. Real alerts will look like this."
    icon, label = _EVENT_LABELS.get(str(event.get("type", "")), ("•", str(event.get("type", ""))))
    who = email or "A recipient"
    where = f' in campaign *{campaign_name}*' if campaign_name else ""
    return f"{icon} VoltPhish: *{who}* {label}{where}."


def build_webhook_body(
    fmt: str, secret: str, event: dict, campaign_name: str | None = None, email: str | None = None
) -> tuple[bytes, dict]:
    """Serialize an event into the wire format for a given webhook type and
    return (body, headers). Shared by live delivery and the 'Send test' action."""
    if fmt == "slack":
        body = json.dumps({"text": _chat_message(event, campaign_name, email)}).encode("utf-8")
        return body, {"Content-Type": "application/json", "User-Agent": "VoltPhish-Webhook/1"}
    if fmt == "teams":
        # Modern Teams "Workflows" incoming webhooks expect an Adaptive Card
        # wrapped as a message attachment (the classic MessageCard connector is
        # retired). This shape works with the "Send webhook alerts to a channel"
        # workflow template.
        text = _chat_message(event, campaign_name, email)
        body = json.dumps(
            {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": {
                            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                            "type": "AdaptiveCard",
                            "version": "1.4",
                            "body": [
                                {
                                    "type": "TextBlock",
                                    "text": "🎣 VoltPhish alert",
                                    "weight": "Bolder",
                                    "size": "Medium",
                                    "color": "Accent",
                                },
                                {"type": "TextBlock", "text": text, "wrap": True},
                            ],
                        },
                    }
                ],
            }
        ).encode("utf-8")
        return body, {"Content-Type": "application/json", "User-Agent": "VoltPhish-Webhook/1"}
    # Generic: our own JSON, HMAC-signed so the receiver can authenticate it.
    body = json.dumps(event, separators=(",", ":")).encode("utf-8")
    signature = webhook_signature(secret, body)
    return body, {
        "Content-Type": "application/json",
        "User-Agent": "VoltPhish-Webhook/1",
        "X-VoltPhish-Event": str(event.get("type", "")),
        "X-VoltPhish-Signature": f"sha256={signature}",
    }
