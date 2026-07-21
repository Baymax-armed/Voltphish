"""Security-awareness training: modules, quiz questions, and enrollments.

A `TrainingModule` is a lesson (HTML content + optional video) with an optional
quiz (`QuizQuestion` rows). Employees are enrolled via `TrainingEnrollment`,
which carries a per-enrollment token so a trainee can open their lesson from a
link without an account. Completion + score drive gamification (points) and the
leaderboard. Trainees are recipients (by email), not admin Users.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import UTCDateTime, utcnow


class Difficulty(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class EnrollmentStatus(str, enum.Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class TrainingModule(Base):
    __tablename__ = "training_modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str] = mapped_column(String(60), default="General", nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty), default=Difficulty.beginner, nullable=False
    )
    content_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    pass_score: Mapped[int] = mapped_column(Integer, default=80, nullable=False)  # percent
    points: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="module", cascade="all, delete-orphan", order_by="QuizQuestion.order"
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("training_modules.id", ondelete="CASCADE"), nullable=False
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON-encoded list[str] of answer options.
    options: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    correct_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    module: Mapped["TrainingModule"] = relationship(back_populates="questions")


class TrainingEnrollment(Base):
    __tablename__ = "training_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("training_modules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus), default=EnrollmentStatus.assigned, nullable=False
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # percent
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Provenance: auto-enrolled from a campaign click, or manually assigned.
    campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    module: Mapped["TrainingModule"] = relationship()
