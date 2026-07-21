"""Background scheduler for time-based campaign launches.

A single asyncio loop wakes periodically, finds `scheduled` campaigns whose
launch time has arrived, and kicks off their send. Because state lives in the
DB, a restart doesn't lose scheduled campaigns — they're re-detected on the next
tick. (For multi-worker production, move to a durable job queue with leader
election so two workers don't double-send; noted in README roadmap.)
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from ..database import SessionLocal
from ..models import Campaign, CampaignStatus, utcnow
from .sender import enqueue_campaign

log = logging.getLogger("phishsim.scheduler")

_TICK_SECONDS = 15


def _launch_due_campaigns() -> int:
    """Find scheduled campaigns whose time has come and enqueue their sends.
    Flipping status to in_progress inside the same transaction ensures a slow
    tick won't double-enqueue on the next pass."""
    db = SessionLocal()
    try:
        now = utcnow()
        rows = db.execute(
            select(Campaign).where(
                Campaign.status == CampaignStatus.scheduled,
                Campaign.launch_at.is_not(None),
                Campaign.launch_at <= now,
            )
        ).scalars()
        count = 0
        for c in rows:
            log.info("scheduler launching campaign %s", c.id)
            enqueue_campaign(db, c)  # sets status in_progress + enqueues jobs
            count += 1
        db.commit()
        return count
    finally:
        db.close()


async def _run_loop() -> None:
    tick = 0
    while True:
        try:
            await asyncio.to_thread(_launch_due_campaigns)
        except Exception:  # noqa: BLE001
            log.exception("scheduler tick failed")
        # Poll the reported-phish mailbox roughly every 60s.
        if tick % 4 == 0:
            try:
                from .imap_monitor import poll_reported

                n = await asyncio.to_thread(poll_reported)
                if n:
                    log.info("IMAP: credited %s recipient(s) as reported", n)
            except Exception:  # noqa: BLE001
                log.exception("IMAP poll failed")
        tick += 1
        await asyncio.sleep(_TICK_SECONDS)


_task: asyncio.Task | None = None


def start_scheduler() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_run_loop())
        log.info("campaign scheduler started (tick=%ss)", _TICK_SECONDS)


def stop_scheduler() -> None:
    if _task is not None:
        _task.cancel()
