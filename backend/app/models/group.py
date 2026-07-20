"""Recipient groups and their targets (the people a simulation is sent to)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import UTCDateTime, utcnow


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )

    targets: Mapped[list["Target"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class Target(Base):
    __tablename__ = "targets"
    __table_args__ = (UniqueConstraint("group_id", "email", name="uq_target_group_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    position: Mapped[str | None] = mapped_column(String(120), nullable=True)

    group: Mapped["Group"] = relationship(back_populates="targets")
