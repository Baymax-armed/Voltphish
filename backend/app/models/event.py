"""Immutable timeline of things that happened in a campaign (audit trail).

Events are append-only (CLAUDE.md A09). We store request context (IP, UA) for
investigation but never the submitted password value."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import UTCDateTime, utcnow


class EventType(str, enum.Enum):
    campaign_created = "campaign_created"
    email_sent = "email_sent"
    email_error = "email_error"
    email_opened = "email_opened"
    clicked_link = "clicked_link"
    submitted_data = "submitted_data"
    reported = "reported"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    # rid string (not FK) so events survive even if a result row is pruned.
    rid: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)

    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # JSON string for extra detail; MUST NOT contain passwords/secrets.
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    campaign: Mapped["object"] = relationship("Campaign", back_populates="events")
