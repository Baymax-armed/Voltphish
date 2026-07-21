"""Campaign send orchestration on top of the durable job queue.

`enqueue_campaign` prepares per-recipient Result rows and enqueues one durable
`send_email` job per recipient (spread across the drip window if send_by_at is
set). The actual sending happens in the queue handler (services/handlers.py), so
sends survive restarts and can be processed by multiple workers.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import Campaign, CampaignStatus, Result, ResultStatus, utcnow
from ..security import new_result_id, new_short_code
from .queue import enqueue

log = logging.getLogger("voltphish.sender")

# Business-hours window (local time in the campaign's timezone).
_BH_START = 9   # 09:00
_BH_END = 17    # 17:00


def _shift_to_business_hours(dt: datetime, tz_name: str) -> datetime:
    """Move a send time into the next Mon–Fri 09:00–17:00 slot in tz_name, so a
    drip that would land at 2am or on a Sunday goes out the next business
    morning instead. Returns an aware-UTC datetime."""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    except Exception:  # noqa: BLE001 — unknown tz name → treat as UTC
        tz = timezone.utc

    local = dt.astimezone(tz)
    for _ in range(14):  # bounded: at most ~2 weeks of shifting
        if local.weekday() >= 5:  # Sat/Sun → next day 09:00
            local = (local + timedelta(days=1)).replace(hour=_BH_START, minute=0, second=0, microsecond=0)
            continue
        if local.hour < _BH_START:
            local = local.replace(hour=_BH_START, minute=0, second=0, microsecond=0)
            continue
        if local.hour >= _BH_END:  # after close → next day 09:00
            local = (local + timedelta(days=1)).replace(hour=_BH_START, minute=0, second=0, microsecond=0)
            continue
        break
    return local.astimezone(timezone.utc)


def _existing_results(db: DbSession, campaign_id: int) -> list[Result]:
    return list(
        db.execute(select(Result).where(Result.campaign_id == campaign_id)).scalars()
    )


def prepare_results(db: DbSession, campaign: Campaign) -> int:
    """Create one Result per recipient (deduped across target groups, minus
    exclusions) if not already present. Returns count."""
    existing = _existing_results(db, campaign.id)
    if existing:
        return len(existing)
    from .audience import campaign_recipient_targets

    targets = campaign_recipient_targets(campaign)
    for target in targets:
        # Append through the relationship so campaign.results stays consistent.
        campaign.results.append(
            Result(
                rid=new_result_id(),
                short_code=new_short_code(),
                email=target.email,
                phone=target.phone,
                first_name=target.first_name,
                last_name=target.last_name,
                position=target.position,
                status=ResultStatus.scheduled,
            )
        )
    db.flush()
    return len(targets)


def enqueue_campaign(db: DbSession, campaign: Campaign) -> int:
    """Prepare results and enqueue a durable send job per recipient. Returns the
    number of emails queued. Caller commits."""
    prepare_results(db, campaign)
    campaign.status = CampaignStatus.in_progress

    results = _existing_results(db, campaign.id)
    n = len(results)
    start = utcnow()
    # Drip: spread run_after evenly across [now, send_by_at]; else all now.
    gap = 0.0
    if campaign.send_by_at is not None and n > 1:
        window = (campaign.send_by_at - start).total_seconds()
        gap = max(window, 0) / (n - 1)

    for i, result in enumerate(results):
        run_after = start + timedelta(seconds=gap * i) if gap else start
        # NG-010: jitter so sends aren't perfectly evenly spaced (attackers
        # don't fire at exact intervals, and a burst trips spam filters). Adds
        # up to ±half a gap; non-security timing so a CSPRNG is more than enough.
        if campaign.send_jitter and gap:
            offset = (secrets.randbelow(int(gap) + 1)) - gap / 2
            run_after = run_after + timedelta(seconds=offset)
            if run_after < start:
                run_after = start
        if campaign.business_hours_only:
            run_after = _shift_to_business_hours(run_after, campaign.send_timezone)
        enqueue(db, "send_email", {"result_id": result.id}, run_after=run_after)
    log.info("campaign %s: queued %s send_email job(s)", campaign.id, n)
    return n
