"""SMS sending profiles: which gateway/provider delivers smishing messages.

Secrets (auth token / api key / secret) are encrypted at rest. Supported
providers: console (test — writes to an outbox, no real send), textbelt (free
tier), twilio, and generic (a custom HTTP gateway for any provider)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import UTCDateTime, utcnow


class SmsProfile(Base):
    __tablename__ = "sms_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)  # console|textbelt|twilio|generic
    from_number: Mapped[str | None] = mapped_column(String(40), nullable=True)  # sender id / from number
    account: Mapped[str | None] = mapped_column(String(255), nullable=True)     # sid / api key / username (non-secret)
    secret_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)  # auth token / key / secret
    config: Mapped[str | None] = mapped_column(Text, nullable=True)             # JSON for the generic provider
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
