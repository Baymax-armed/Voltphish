"""Email templates. Bodies support {{.FirstName}}-style personalization tokens
rendered safely at send time (see services/renderer.py)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import UTCDateTime, utcnow


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    # "email" (subject+html/text) or "sms" (uses `text` as the message body).
    channel: Mapped[str] = mapped_column(String(10), default="email", nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    envelope_sender: Mapped[str | None] = mapped_column(String(320), nullable=True)
    html: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )

    attachments: Mapped[list["object"]] = relationship(
        "Attachment", back_populates="template", cascade="all, delete-orphan"
    )
