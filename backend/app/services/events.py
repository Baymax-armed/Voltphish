"""Helpers to append audit events and advance result status monotonically."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import Event, EventType, Result, ResultStatus, Webhook, utcnow
from ..models.result import status_rank
from .queue import enqueue

# Which event maps to which (candidate) result status.
_EVENT_TO_STATUS = {
    EventType.email_sent: ResultStatus.sent,
    EventType.email_error: ResultStatus.error,
    EventType.email_opened: ResultStatus.opened,
    EventType.clicked_link: ResultStatus.clicked,
    EventType.submitted_data: ResultStatus.submitted,
    EventType.reported: ResultStatus.reported,
}


def record_event(
    db: DbSession,
    *,
    campaign_id: int,
    rid: str | None,
    type: EventType,
    ip: str | None = None,
    user_agent: str | None = None,
    details: dict | None = None,
) -> Event:
    """Append an event and, if it maps to a status, advance the result forward
    only (never regress: a click stays 'clicked' even if a later pixel loads)."""
    event = Event(
        campaign_id=campaign_id,
        rid=rid,
        type=type,
        ip=(ip or None),
        user_agent=(user_agent or "")[:500] or None,
        details=json.dumps(details) if details else None,
    )
    db.add(event)

    if rid and type in _EVENT_TO_STATUS:
        result = db.query(Result).filter(Result.rid == rid).one_or_none()
        if result is not None:
            candidate = _EVENT_TO_STATUS[type]
            # 'reported' and 'error' are always allowed to set; others advance.
            if candidate in (ResultStatus.reported, ResultStatus.error) or (
                status_rank(candidate) > status_rank(result.status)
            ):
                result.status = candidate
            result.last_event_at = utcnow()

    _fan_out_webhooks(db, campaign_id=campaign_id, rid=rid, type=type, ip=ip)
    return event


def _fan_out_webhooks(
    db: DbSession, *, campaign_id: int, rid: str | None, type: EventType, ip: str | None
) -> None:
    """Enqueue a durable delivery job for each active webhook (part of the same
    transaction as the event, so events and their webhooks commit together)."""
    hooks = db.execute(select(Webhook).where(Webhook.is_active.is_(True))).scalars().all()
    if not hooks:
        return
    event_payload = {
        "type": type.value,
        "campaign_id": campaign_id,
        "rid": rid,
        "ip": ip,
        "time": utcnow().isoformat(),
    }
    for hook in hooks:
        enqueue(db, "deliver_webhook", {"webhook_id": hook.id, "event": event_payload})
