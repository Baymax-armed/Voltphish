"""Landing pages: the custom HTML a recipient sees after clicking a link.

Forms on the page post back to the tracking server, which records that a
submission occurred. Per the project's ethical guardrail, submitted passwords
are never stored (see phish/server.py and VOLTPHISH_CAPTURE_PASSWORDS)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import UTCDateTime, utcnow


class LandingPage(Base):
    __tablename__ = "landing_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    html: Mapped[str] = mapped_column(Text, nullable=False)
    # Where the browser goes after submitting the form (an awareness page).
    redirect_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
