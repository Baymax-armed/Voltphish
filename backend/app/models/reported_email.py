"""Emails reported by employees through the Report-Phish add-in.

Two kinds land here:
  - a reported VoltPhish *simulation* (matched by tracking token) — the reporter
    is credited as a Security Champion (a `reported` event is recorded), and we
    keep a row here flagged `is_simulation=True` for the record.
  - a reported *real* suspicious email (no tracking token) — queued for the
    security team to triage. This is the SOC-input side of a report button.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import UTCDateTime, utcnow


class ReportStatus(str, enum.Enum):
    new = "new"
    reviewing = "reviewing"
    malicious = "malicious"
    benign = "benign"
    closed = "closed"


class ReportedEmail(Base):
    __tablename__ = "reported_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_email: Mapped[str | None] = mapped_column(String(320), index=True, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(998), nullable=True)
    sender: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Trimmed for storage — we keep a preview, never the full raw body (privacy).
    body_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    headers: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="addin", nullable=False)  # addin | imap | manual
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    matched_rid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    matched_result_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus), default=ReportStatus.new, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
