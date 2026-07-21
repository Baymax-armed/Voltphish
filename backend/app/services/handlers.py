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

log = logging.getLogger("voltphish.handlers")
settings = get_settings()

_TERMINAL_DELIVERED = {
    ResultStatus.sent, ResultStatus.opened, ResultStatus.clicked,
    ResultStatus.submitted, ResultStatus.reported,
}


_TEXT_ATTACH_EXT = (".ics", ".html", ".htm", ".txt", ".csv", ".vcf", ".eml")


def build_attachments(template, ctx=None) -> list[tuple[str, str, bytes]]:  # noqa: ANN001
    """Decode a template's stored attachments into (name, content_type, bytes).
    Text-based attachments (e.g. a calendar .ics lure) get their personalization
    tokens rendered per recipient, so {{.URL}} becomes that recipient's link."""
    out: list[tuple[str, str, bytes]] = []
    for att in getattr(template, "attachments", []) or []:
        try:
            raw = base64.b64decode(att.content_b64)
        except (binascii.Error, ValueError):
            continue
        is_text = (att.content_type or "").startswith("text/") or att.filename.lower().endswith(_TEXT_ATTACH_EXT)
        if ctx is not None and is_text:
            try:
                raw = render_text(raw.decode("utf-8"), ctx).encode("utf-8")
            except UnicodeDecodeError:
                pass
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
                    attachments=build_attachments(template, ctx),
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


def _training_invite_html(title: str, link: str) -> str:
    import html as _html

    t = _html.escape(title)
    return (
        '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:560px;margin:0 auto;color:#1a1a1a;line-height:1.55">'
        '<h2 style="font-size:19px;margin:0 0 10px">Security awareness training assigned</h2>'
        f'<p>You’ve been assigned a short training module: <strong>{t}</strong>. It only takes a few minutes.</p>'
        f'<p style="margin:18px 0"><a href="{link}" style="display:inline-block;background:#1f5fd6;color:#fff;'
        'text-decoration:none;padding:12px 26px;border-radius:8px;font-weight:600">Start training</a></p>'
        f'<p style="color:#666;font-size:13px">Or open this link: {link}</p></div>'
    )


@register("send_training_invite")
async def handle_send_training_invite(payload: dict) -> None:
    """Email one enrolled recipient their unique training link."""
    from ..models import SendingProfile, TrainingEnrollment, TrainingModule

    db = SessionLocal()
    try:
        enr = db.get(TrainingEnrollment, int(payload["enrollment_id"]))
        if enr is None:
            return
        module = db.get(TrainingModule, enr.module_id)
        profile = db.get(SendingProfile, int(payload["profile_id"]))
        if module is None or profile is None:
            return
        base = str(payload.get("base", "")).rstrip("/")
        link = f"{base}/train/{enr.token}"
        await send_email(
            OutgoingEmail(
                to_address=enr.email, from_address=profile.from_address,
                subject=f"Security training assigned: {module.title}",
                html=_training_invite_html(module.title, link),
                text=f"You've been assigned security training: {module.title}\n\nStart here: {link}",
                envelope_from=profile.envelope_sender, extra_headers=profile_headers(profile),
            ),
            profile,
        )
        log.info("training invite sent to %s (module %s)", enr.email, module.id)
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


def _record_webhook_health(webhook_id: int, status_code: int | None, error: str | None) -> None:
    """Persist the last delivery outcome so the UI reflects real health."""
    db = SessionLocal()
    try:
        w = db.get(Webhook, webhook_id)
        if w is not None:
            w.last_attempt_at = utcnow()
            w.last_status = status_code
            w.last_error = (error or None) and error[:500]
            db.commit()
    finally:
        db.close()


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
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
            resp = await client.post(url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        _record_webhook_health(webhook_id, None, f"unreachable ({type(exc).__name__})")
        raise  # let the queue retry with backoff
    if resp.status_code >= 400:
        _record_webhook_health(webhook_id, resp.status_code, f"HTTP {resp.status_code}")
        raise RuntimeError(f"webhook returned HTTP {resp.status_code}")  # queue retries
    _record_webhook_health(webhook_id, resp.status_code, None)


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
