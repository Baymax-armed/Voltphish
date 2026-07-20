"""Outbound webhooks: POST campaign events to external systems, HMAC-signed.

The signing secret is encrypted at rest (AES-256-GCM). Delivery goes through the
durable job queue with retries and an SSRF guard on the target URL."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import UTCDateTime, utcnow


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Ciphertext of the HMAC secret; never returned by the API.
    secret_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Payload format: 'generic' (our signed JSON), 'slack', or 'teams'.
    format: Mapped[str] = mapped_column(String(20), default="generic", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
