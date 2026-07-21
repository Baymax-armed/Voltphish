"""Campaigns tie together a template, a sending profile, and a target group."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, Enum, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import UTCDateTime, utcnow

# NG-001: a campaign can target several groups and exclude (suppress) others.
# The legacy single `group_id` column stays as the "primary" group for backward
# compatibility; the real recipient set is the union of target_groups minus
# exclude_groups (see services.audience.campaign_recipient_targets).
campaign_target_groups = Table(
    "campaign_target_groups", Base.metadata,
    Column("campaign_id", ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
)
campaign_exclude_groups = Table(
    "campaign_exclude_groups", Base.metadata,
    Column("campaign_id", ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
)


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    error = "error"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.draft, nullable=False
    )

    # Delivery channel — always "email" (kept for schema stability).
    channel: Mapped[str] = mapped_column(String(10), default="email", nullable=False)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"), nullable=False)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("sending_profiles.id"), nullable=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    # Optional custom landing page. When null, a click redirects to redirect_url
    # (if set) or the built-in awareness page.
    page_id: Mapped[int | None] = mapped_column(ForeignKey("landing_pages.id"), nullable=True)

    # Governance: recorded at launch — who authorized the test and a reference
    # to the authorization (ticket / signed scope). Kept for the audit trail.
    authorized_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    authorization_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Base URL recipients' clicks resolve to (the authorized test host).
    phish_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Where a clicked link ultimately lands (Phase 1: an external teaching page).
    redirect_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Just-in-time remediation: auto-enrol a recipient who fails this campaign into
    # a training module. Trigger: off | clicked | submitted (submitted-only ignores
    # plain clicks). If auto_enroll_email, the training link is emailed via the
    # campaign's sending profile. Module null => adaptive pick by behaviour.
    auto_enroll_trigger: Mapped[str] = mapped_column(String(12), default="off", nullable=False)
    auto_enroll_module_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_modules.id", ondelete="SET NULL"), nullable=True
    )
    auto_enroll_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    launch_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # If set, sends are spread (dripped) evenly across [launch_at, send_by_at].
    send_by_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # NG-010: realism. Jitter randomises each send time so they aren't perfectly
    # evenly spaced; business_hours_only shifts sends into Mon–Fri 09:00–17:00 in
    # send_timezone (IANA name, e.g. "Asia/Kolkata"; empty = UTC).
    send_jitter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    business_hours_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    send_timezone: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    template: Mapped["object"] = relationship("Template")
    profile: Mapped["object"] = relationship("SendingProfile")
    group: Mapped["object"] = relationship("Group")
    # NG-001: full include/exclude group sets (primary `group` kept for compat).
    target_groups: Mapped[list["object"]] = relationship("Group", secondary=campaign_target_groups)
    exclude_groups: Mapped[list["object"]] = relationship("Group", secondary=campaign_exclude_groups)
    page: Mapped["object"] = relationship("LandingPage")
    results: Mapped[list["object"]] = relationship(
        "Result", back_populates="campaign", cascade="all, delete-orphan"
    )
    events: Mapped[list["object"]] = relationship(
        "Event", back_populates="campaign", cascade="all, delete-orphan"
    )

    @property
    def target_group_ids(self) -> list[int]:
        ids = [g.id for g in self.target_groups] if self.target_groups else []
        if not ids and self.group_id:
            ids = [self.group_id]
        return ids

    @property
    def exclude_group_ids(self) -> list[int]:
        return [g.id for g in self.exclude_groups]
