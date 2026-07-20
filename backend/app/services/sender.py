"""Campaign send orchestration on top of the durable job queue.

`enqueue_campaign` prepares per-recipient Result rows and enqueues one durable
`send_email` job per recipient (spread across the drip window if send_by_at is
set). The actual sending happens in the queue handler (services/handlers.py), so
sends survive restarts and can be processed by multiple workers.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import Campaign, CampaignStatus, Result, ResultStatus, utcnow
from ..security import new_result_id, new_short_code
from .queue import enqueue

log = logging.getLogger("phishsim.sender")


def _existing_results(db: DbSession, campaign_id: int) -> list[Result]:
    return list(
        db.execute(select(Result).where(Result.campaign_id == campaign_id)).scalars()
    )


def prepare_results(db: DbSession, campaign: Campaign) -> int:
    """Create one Result per target if not already present. Returns count."""
    existing = _existing_results(db, campaign.id)
    if existing:
        return len(existing)
    for target in campaign.group.targets:
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
    return len(campaign.group.targets)


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

    from datetime import timedelta

    job_type = "send_sms" if campaign.channel == "sms" else "send_email"
    for i, result in enumerate(results):
        run_after = start + timedelta(seconds=gap * i) if gap else start
        enqueue(db, job_type, {"result_id": result.id}, run_after=run_after)
    log.info("campaign %s: queued %s %s job(s)", campaign.id, n, job_type)
    return n
