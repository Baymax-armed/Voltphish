"""Sending profiles: SMTP configuration used to deliver simulation emails.

The SMTP password is encrypted at rest (AES-256-GCM, see security.encrypt_secret)
and is never returned by the API in plaintext.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import UTCDateTime, utcnow


class SendingProfile(Base):
    __tablename__ = "sending_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    # Display "From" shown to the recipient (can be spoofed for a simulation).
    from_address: Mapped[str] = mapped_column(String(320), nullable=False)
    # Envelope sender (SMTP MAIL FROM / Return-Path) used for SPF + bounces.
    # Should be an address the SMTP server is authorized to send as. If empty,
    # the display From is used. Separating the two lets you show a spoofed From
    # while still passing SPF via an authorized envelope address.
    envelope_sender: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # "smtp" (default) or "api" (send over HTTPS via an email provider — useful
    # when outbound SMTP ports are firewalled).
    kind: Mapped[str] = mapped_column(String(10), default="smtp", nullable=False)

    # SMTP fields (nullable so API profiles don't need them).
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, default=587, nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Ciphertext only. Plaintext never touches the DB (CLAUDE.md A02/A09).
    password_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Email-API fields.
    api_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)  # sendgrid|brevo|...
    api_key_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    api_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)   # mailgun needs this

    # Extra SMTP headers as a JSON list of {"key","value"} (e.g. X-Mailer).
    headers: Mapped[str | None] = mapped_column(Text, nullable=True)

    use_starttls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Never default to ignoring cert errors (CLAUDE.md A02). Opt-in only.
    ignore_cert_errors: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
