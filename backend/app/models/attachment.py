"""Template attachments. Stored base64-encoded in the DB (small files only).

For an authorized simulation these mimic lure documents (fake invoice, etc.).
An extension allowlist blocks executables/scripts and a size cap is enforced at
the API layer."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import UTCDateTime, utcnow


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False)
    content_b64: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    template: Mapped["object"] = relationship("Template", back_populates="attachments")
