"""Durable background job (the persistent task queue).

Jobs live in the DB so they survive restarts and can be shared across worker
processes. Workers claim a job atomically with an optimistic UPDATE guarded on
status, so a job is executed by exactly one worker even with several running
(true parallelism requires a real concurrent DB like Postgres; SQLite serializes
writers but jobs are still durable and restart-safe)."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import UTCDateTime, utcnow


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.queued.value, index=True, nullable=False)

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Not eligible to run until this time (used for scheduling + retry backoff).
    run_after: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True, nullable=False)
    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)
