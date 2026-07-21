"""User accounts and server-side sessions."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import UTCDateTime, utcnow


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.operator, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # When true, the user is forced to set a new password before using the app
    # (e.g. after the generated first-run password or an admin reset).
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Two-factor auth (TOTP). Secret is AES-256-GCM encrypted at rest; a secret
    # may exist while pending enrollment — `totp_enabled` gates the login check.
    totp_secret_enc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Last accepted TOTP time-step — a code at step N can't be replayed (RFC 6238).
    totp_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Granular RBAC: extra capabilities granted to a non-admin (CSV of permission
    # keys). Admins implicitly hold every permission; this delegates specific
    # admin areas (e.g. "users:manage") to an operator without full admin.
    extra_permissions: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    """Opaque server-side session. The cookie holds the raw token; we store its
    SHA-256 so a DB leak alone can't resume sessions (CLAUDE.md A07)."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # Per-session CSRF token (double-submit). Returned to the SPA in the login
    # body / /me and required as X-CSRF-Token on state-changing requests.
    csrf_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    # Non-sensitive request context for audit (no full request bodies).
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
