"""Durable job queue: enqueue + worker loop with atomic claiming and retries.

Handlers are async `async def handler(payload: dict) -> None`; raising triggers a
retry with exponential backoff until max_attempts, after which the job is marked
`failed`. Jobs are claimed with an optimistic, status-guarded UPDATE so exactly
one worker runs a given job.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
from collections.abc import Awaitable, Callable
from datetime import timedelta

from sqlalchemy import select, update

from ..database import SessionLocal
from ..models import Job, JobStatus, utcnow

log = logging.getLogger("voltphish.queue")

Handler = Callable[[dict], Awaitable[None]]
_HANDLERS: dict[str, Handler] = {}

_POLL_SECONDS = 1.0
_WORKER_CONCURRENCY = 4
_tasks: list[asyncio.Task] = []
_stopping = False


def register(job_type: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _HANDLERS[job_type] = fn
        return fn
    return deco


def enqueue(db, job_type: str, payload: dict, *, run_after=None, max_attempts: int = 5) -> Job:
    """Insert a job. Caller commits (so it can be part of a larger transaction)."""
    job = Job(
        type=job_type,
        payload=json.dumps(payload),
        run_after=run_after or utcnow(),
        max_attempts=max_attempts,
    )
    db.add(job)
    return job


def _claim_one(worker_id: str) -> int | None:
    db = SessionLocal()
    try:
        now = utcnow()
        candidate = db.execute(
            select(Job.id)
            .where(Job.status == JobStatus.queued.value, Job.run_after <= now)
            .order_by(Job.run_after)
            .limit(1)
        ).scalar_one_or_none()
        if candidate is None:
            return None
        # Guard on status so a concurrent worker can't double-claim.
        res = db.execute(
            update(Job)
            .where(Job.id == candidate, Job.status == JobStatus.queued.value)
            .values(status=JobStatus.running.value, locked_by=worker_id,
                    locked_at=now, attempts=Job.attempts + 1, updated_at=now)
        )
        db.commit()
        return candidate if res.rowcount == 1 else None
    finally:
        db.close()


def _load_job(job_id: int) -> tuple[str, dict, int, int] | None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return None
        return job.type, json.loads(job.payload), job.attempts, job.max_attempts
    finally:
        db.close()


def _finish(job_id: int, *, ok: bool, error: str | None, attempts: int, max_attempts: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        if ok:
            job.status = JobStatus.done.value
        elif attempts >= max_attempts:
            job.status = JobStatus.failed.value
            job.last_error = (error or "")[:500]
        else:
            # Retry with exponential backoff (2^attempts seconds, capped).
            job.status = JobStatus.queued.value
            job.last_error = (error or "")[:500]
            job.run_after = utcnow() + timedelta(seconds=min(2 ** attempts, 300))
        job.locked_by = None
        db.commit()
    finally:
        db.close()


async def _run_job(job_id: int) -> None:
    loaded = await asyncio.to_thread(_load_job, job_id)
    if loaded is None:
        return
    job_type, payload, attempts, max_attempts = loaded
    handler = _HANDLERS.get(job_type)
    if handler is None:
        await asyncio.to_thread(
            _finish, job_id, ok=False, error=f"no handler for '{job_type}'",
            attempts=max_attempts, max_attempts=max_attempts,
        )
        return
    try:
        await handler(payload)
        await asyncio.to_thread(_finish, job_id, ok=True, error=None,
                                attempts=attempts, max_attempts=max_attempts)
    except Exception as exc:  # noqa: BLE001
        log.warning("job %s (%s) failed attempt %s: %s", job_id, job_type, attempts, exc)
        await asyncio.to_thread(_finish, job_id, ok=False, error=f"{type(exc).__name__}: {exc}",
                                attempts=attempts, max_attempts=max_attempts)


async def _worker(worker_id: str) -> None:
    while not _stopping:
        try:
            job_id = await asyncio.to_thread(_claim_one, worker_id)
            if job_id is None:
                await asyncio.sleep(_POLL_SECONDS)
                continue
            await _run_job(job_id)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("worker %s loop error", worker_id)
            await asyncio.sleep(_POLL_SECONDS)


def _requeue_orphans() -> None:
    """On startup, reset jobs left 'running' by a crashed worker back to queued."""
    db = SessionLocal()
    try:
        db.execute(
            update(Job).where(Job.status == JobStatus.running.value).values(
                status=JobStatus.queued.value, locked_by=None
            )
        )
        db.commit()
    finally:
        db.close()


def start_workers() -> None:
    global _stopping
    _stopping = False
    _requeue_orphans()
    # Import handlers here so their @register decorators run before we consume.
    from . import handlers  # noqa: F401

    for i in range(_WORKER_CONCURRENCY):
        _tasks.append(asyncio.create_task(_worker(f"w{i}-{secrets.token_hex(3)}")))
    log.info("job queue workers started (n=%s)", _WORKER_CONCURRENCY)


def stop_workers() -> None:
    global _stopping
    _stopping = True
    for t in _tasks:
        t.cancel()
    _tasks.clear()
