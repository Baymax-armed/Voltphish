"""Per-recipient results. One Result per (campaign, target). The `rid` is the
unguessable token embedded in that recipient's email and tracking links."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import UTCDateTime, utcnow


class ResultStatus(str, enum.Enum):
    scheduled = "scheduled"
    sending = "sending"
    sent = "sent"
    opened = "opened"
    clicked = "clicked"
    submitted = "submitted"   # entered data on landing page (simulation)
    reported = "reported"     # recipient reported the phish (good outcome!)
    error = "error"


# Ordered by "progression" so we never regress a recipient's status
# (a click after an open shouldn't drop back to opened).
_STATUS_RANK = {
    ResultStatus.scheduled: 0,
    ResultStatus.sending: 1,
    ResultStatus.sent: 2,
    ResultStatus.opened: 3,
    ResultStatus.clicked: 4,
    ResultStatus.submitted: 5,
    ResultStatus.error: 6,
    ResultStatus.reported: 7,
}


def status_rank(status: ResultStatus) -> int:
    return _STATUS_RANK[status]


class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    rid: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # Short click-tracking code for SMS (keeps links short: /s/{code}).
    short_code: Mapped[str | None] = mapped_column(String(16), unique=True, index=True, nullable=True)

    # Snapshot of the target at send time (targets may change/be deleted later).
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    position: Mapped[str | None] = mapped_column(String(120), nullable=True)

    status: Mapped[ResultStatus] = mapped_column(
        Enum(ResultStatus), default=ResultStatus.scheduled, nullable=False
    )
    send_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Set when the recipient acknowledges the just-in-time training page.
    trained_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Set when the recipient opens a tracked attachment (e.g. a lure document).
    attachment_opened_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    campaign: Mapped["object"] = relationship("Campaign", back_populates="results")
