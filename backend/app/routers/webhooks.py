"""Outbound webhook CRUD. Admin only. Secrets are encrypted at rest and never
returned. The delivery URL is checked against the SSRF guard at send time."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

import httpx

from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user
from ..permissions import require_permission

require_admin = require_permission("webhooks:manage")
from ..models import Webhook, utcnow
from ..schemas.common import Message
from ..schemas.webhook import WebhookCreate, WebhookOut, WebhookUpdate
from ..security import decrypt_secret, encrypt_secret
from ..services.handlers import build_webhook_body
from ..services.ssrf import SsrfError, validate_url

router = APIRouter(
    prefix="/api/v1/webhooks",
    tags=["webhooks"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect), Depends(require_admin)],
)


def _to_out(w: Webhook) -> WebhookOut:
    return WebhookOut(
        id=w.id, name=w.name, url=w.url, is_active=w.is_active,
        has_secret=bool(w.secret_encrypted), format=getattr(w, "format", "generic"),
        created_at=w.created_at, modified_at=w.modified_at,
    )


def _check_url(url: str) -> None:
    # Reject obviously-unsafe targets at save time (also re-checked at delivery).
    try:
        validate_url(url)
    except SsrfError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"URL rejected: {exc}")


@router.get("", response_model=list[WebhookOut])
def list_webhooks(db: DbSession = Depends(get_db)) -> list[WebhookOut]:
    return [_to_out(w) for w in db.execute(select(Webhook).order_by(Webhook.name)).scalars()]


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
def create_webhook(payload: WebhookCreate, db: DbSession = Depends(get_db)) -> WebhookOut:
    _check_url(str(payload.url))
    w = Webhook(
        name=payload.name, url=str(payload.url),
        secret_encrypted=encrypt_secret(payload.secret), is_active=payload.is_active,
        format=payload.format,
    )
    db.add(w)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A webhook with that name already exists")
    db.refresh(w)
    return _to_out(w)


@router.put("/{webhook_id}", response_model=WebhookOut)
def update_webhook(webhook_id: int, payload: WebhookUpdate, db: DbSession = Depends(get_db)) -> WebhookOut:
    w = db.get(Webhook, webhook_id)
    if w is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    _check_url(str(payload.url))
    w.name = payload.name
    w.url = str(payload.url)
    w.is_active = payload.is_active
    w.format = payload.format
    if payload.secret is not None:
        w.secret_encrypted = encrypt_secret(payload.secret) if payload.secret else None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A webhook with that name already exists")
    db.refresh(w)
    return _to_out(w)


@router.post("/{webhook_id}/test", response_model=Message)
async def test_webhook(webhook_id: int, db: DbSession = Depends(get_db)) -> Message:
    """Send a sample notification to the webhook so the operator can confirm the
    URL actually works before trusting it for live alerts."""
    w = db.get(Webhook, webhook_id)
    if w is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    try:
        validate_url(w.url)
    except SsrfError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"URL rejected: {exc}")

    secret = decrypt_secret(w.secret_encrypted) or ""
    fmt = getattr(w, "format", "generic")
    event = {
        "type": "submitted_data",
        "campaign_id": 0,
        "rid": "test",
        "ip": "203.0.113.10",
        "time": utcnow().isoformat(),
        "test": True,
    }
    body, headers = build_webhook_body(
        fmt, secret, event, campaign_name="VoltPhish connection test", email="test.user@example.com"
    )

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
            resp = await client.post(w.url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Couldn't reach that URL. Make sure it's a valid Incoming Webhook URL "
            f"(not a channel or chat link). [{type(exc).__name__}]",
        )
    if resp.status_code >= 400:
        hint = ""
        if fmt in ("slack", "teams"):
            hint = (
                " For Teams this must be an Incoming Webhook / Workflow URL "
                "(…webhook.office.com… or …logic.azure.com…), not a teams.microsoft.com chat link."
            )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"The URL returned HTTP {resp.status_code}, so the test message was not delivered.{hint}",
        )
    return Message(detail=f"Test notification delivered (HTTP {resp.status_code}). Check your channel.")


@router.delete("/{webhook_id}", response_model=Message)
def delete_webhook(webhook_id: int, db: DbSession = Depends(get_db)) -> Message:
    w = db.get(Webhook, webhook_id)
    if w is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    db.delete(w)
    db.commit()
    return Message(detail="Webhook deleted")
