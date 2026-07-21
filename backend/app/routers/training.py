"""Admin CRUD for training modules, assignment, and completion analytics."""
from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user
from ..permissions import require_permission

require_admin = require_permission("training:manage")
from ..models import (
    Difficulty,
    EnrollmentStatus,
    Group,
    QuizQuestion,
    Result,
    Target,
    TrainingEnrollment,
    TrainingModule,
)
from ..models.base import utcnow
from ..schemas.common import Message

router = APIRouter(
    prefix="/api/v1/training", tags=["training"], dependencies=[Depends(get_current_user)]
)


# ── schemas ───────────────────────────────────────────────────────────────────
class QuestionIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    options: list[str] = Field(min_length=2, max_length=8)
    correct_index: int = Field(ge=0)


class QuestionOut(BaseModel):
    id: int
    prompt: str
    options: list[str]
    correct_index: int
    order: int


class ModuleIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    category: str = Field(default="General", max_length=60)
    difficulty: Difficulty = Difficulty.beginner
    content_html: str = Field(default="", max_length=200_000)
    video_url: str | None = Field(default=None, max_length=500)
    estimated_minutes: int = Field(default=5, ge=1, le=180)
    pass_score: int = Field(default=80, ge=0, le=100)
    points: int = Field(default=100, ge=0, le=10_000)
    is_published: bool = True
    questions: list[QuestionIn] = Field(default_factory=list)


class ModuleOut(BaseModel):
    id: int
    title: str
    description: str | None
    category: str
    difficulty: Difficulty
    content_html: str
    video_url: str | None
    estimated_minutes: int
    pass_score: int
    points: int
    is_published: bool
    questions: list[QuestionOut]
    enrolled: int = 0
    completed: int = 0


class EnrollmentOut(BaseModel):
    id: int
    module_id: int
    module_title: str
    email: str
    token: str
    status: EnrollmentStatus
    score: int | None
    attempts: int
    assigned_at: str
    completed_at: str | None


# Campaign-outcome → who to remediate. The core "train the people who failed"
# loop. The outcome→who mapping lives in services.audience so 'save as group'
# uses exactly the same definitions.
from ..services.audience import campaign_emails as _campaign_emails  # noqa: E402


class AssignIn(BaseModel):
    emails: list[str] = Field(default_factory=list)
    group_id: int | None = None
    # Remediation targeting: enroll a campaign's audience, optionally by outcome.
    campaign_id: int | None = None
    outcome: str = "all"  # all | clicked | submitted | opened | reported | no_action


class AudienceIn(BaseModel):
    campaign_id: int
    outcome: str = "all"


class AudienceOut(BaseModel):
    count: int          # unique recipients matching the outcome
    total: int          # total recipients in the campaign


class LeaderboardRow(BaseModel):
    email: str
    points: int
    completed: int


class TrainingSummary(BaseModel):
    modules: int
    enrollments: int
    completed: int
    completion_rate: int  # percent


def _q_out(q: QuizQuestion) -> QuestionOut:
    return QuestionOut(
        id=q.id, prompt=q.prompt, options=json.loads(q.options or "[]"),
        correct_index=q.correct_index, order=q.order,
    )


def _counts(db: DbSession, module_id: int) -> tuple[int, int]:
    enrolled = db.execute(
        select(func.count(TrainingEnrollment.id)).where(TrainingEnrollment.module_id == module_id)
    ).scalar_one()
    completed = db.execute(
        select(func.count(TrainingEnrollment.id)).where(
            TrainingEnrollment.module_id == module_id,
            TrainingEnrollment.status == EnrollmentStatus.completed,
        )
    ).scalar_one()
    return enrolled, completed


def _m_out(db: DbSession, m: TrainingModule) -> ModuleOut:
    enrolled, completed = _counts(db, m.id)
    return ModuleOut(
        id=m.id, title=m.title, description=m.description, category=m.category,
        difficulty=m.difficulty, content_html=m.content_html, video_url=m.video_url,
        estimated_minutes=m.estimated_minutes, pass_score=m.pass_score, points=m.points,
        is_published=m.is_published, questions=[_q_out(q) for q in m.questions],
        enrolled=enrolled, completed=completed,
    )


def _validate_questions(questions: list[QuestionIn]) -> None:
    for i, q in enumerate(questions):
        if q.correct_index >= len(q.options):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Question {i + 1}: correct_index out of range")


# ── module CRUD ───────────────────────────────────────────────────────────────
@router.get("/modules", response_model=list[ModuleOut])
def list_modules(db: DbSession = Depends(get_db)) -> list[ModuleOut]:
    mods = db.execute(select(TrainingModule).order_by(TrainingModule.id)).scalars().all()
    return [_m_out(db, m) for m in mods]


@router.post("/modules", response_model=ModuleOut, dependencies=[Depends(require_admin), Depends(csrf_protect)])
def create_module(payload: ModuleIn, db: DbSession = Depends(get_db)) -> ModuleOut:
    _validate_questions(payload.questions)
    m = TrainingModule(
        title=payload.title, description=payload.description, category=payload.category,
        difficulty=payload.difficulty, content_html=payload.content_html, video_url=payload.video_url,
        estimated_minutes=payload.estimated_minutes, pass_score=payload.pass_score,
        points=payload.points, is_published=payload.is_published,
        created_at=utcnow(), modified_at=utcnow(),
    )
    db.add(m)
    db.flush()
    for i, q in enumerate(payload.questions):
        db.add(QuizQuestion(module_id=m.id, prompt=q.prompt, options=json.dumps(q.options),
                            correct_index=q.correct_index, order=i))
    db.commit()
    db.refresh(m)
    return _m_out(db, m)


@router.get("/modules/{module_id}", response_model=ModuleOut)
def get_module(module_id: int, db: DbSession = Depends(get_db)) -> ModuleOut:
    m = db.get(TrainingModule, module_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found")
    return _m_out(db, m)


@router.put("/modules/{module_id}", response_model=ModuleOut, dependencies=[Depends(require_admin), Depends(csrf_protect)])
def update_module(module_id: int, payload: ModuleIn, db: DbSession = Depends(get_db)) -> ModuleOut:
    m = db.get(TrainingModule, module_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found")
    _validate_questions(payload.questions)
    m.title = payload.title
    m.description = payload.description
    m.category = payload.category
    m.difficulty = payload.difficulty
    m.content_html = payload.content_html
    m.video_url = payload.video_url
    m.estimated_minutes = payload.estimated_minutes
    m.pass_score = payload.pass_score
    m.points = payload.points
    m.is_published = payload.is_published
    m.modified_at = utcnow()
    # Replace questions wholesale (simplest correct approach for an editor).
    for q in list(m.questions):
        db.delete(q)
    db.flush()
    for i, q in enumerate(payload.questions):
        db.add(QuizQuestion(module_id=m.id, prompt=q.prompt, options=json.dumps(q.options),
                            correct_index=q.correct_index, order=i))
    db.commit()
    db.refresh(m)
    return _m_out(db, m)


@router.delete("/modules/{module_id}", response_model=Message, dependencies=[Depends(require_admin), Depends(csrf_protect)])
def delete_module(module_id: int, db: DbSession = Depends(get_db)) -> Message:
    m = db.get(TrainingModule, module_id)
    if m is not None:
        db.delete(m)
        db.commit()
    return Message(detail="Deleted")


# ── assignment ────────────────────────────────────────────────────────────────
@router.post("/modules/{module_id}/assign", response_model=Message, dependencies=[Depends(csrf_protect)])
def assign_module(module_id: int, payload: AssignIn, db: DbSession = Depends(get_db)) -> Message:
    m = db.get(TrainingModule, module_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found")

    emails: set[str] = {e.strip().lower() for e in payload.emails if e and "@" in e}
    if payload.group_id is not None:
        rows = db.execute(select(Target.email).where(Target.group_id == payload.group_id)).all()
        emails |= {r[0].strip().lower() for r in rows if r[0]}
    if payload.campaign_id is not None:
        emails |= _campaign_emails(db, payload.campaign_id, payload.outcome)
    if not emails:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No valid recipients to assign")

    created = 0
    for email in emails:
        # Skip if there's already an open (not completed) enrollment for this module.
        existing = db.execute(
            select(TrainingEnrollment.id).where(
                TrainingEnrollment.module_id == module_id,
                TrainingEnrollment.email == email,
                TrainingEnrollment.status != EnrollmentStatus.completed,
            )
        ).first()
        if existing:
            continue
        db.add(TrainingEnrollment(module_id=module_id, email=email, token=secrets.token_urlsafe(24)))
        created += 1
    db.commit()
    return Message(detail=f"Assigned to {created} recipient(s).")


@router.post("/audience", response_model=AudienceOut)
def audience_preview(payload: AudienceIn, db: DbSession = Depends(get_db)) -> AudienceOut:
    """Preview how many of a campaign's recipients match an outcome — so the UI
    can show 'this will enroll 7 of 20' before assigning."""
    total = db.execute(
        select(func.count(Result.id)).where(Result.campaign_id == payload.campaign_id)
    ).scalar_one()
    return AudienceOut(count=len(_campaign_emails(db, payload.campaign_id, payload.outcome)), total=total)


class SendInvitesIn(BaseModel):
    profile_id: int
    only_pending: bool = True


@router.post("/modules/{module_id}/send", response_model=Message, dependencies=[Depends(csrf_protect)])
def send_invites(
    module_id: int, payload: SendInvitesIn, request: Request, db: DbSession = Depends(get_db)
) -> Message:
    """Email each enrolled recipient their unique training link, via a sending
    profile. Delivery goes through the durable job queue (restart-safe)."""
    from ..models import SendingProfile
    from ..services.queue import enqueue

    module = db.get(TrainingModule, module_id)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found")
    if db.get(SendingProfile, payload.profile_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sending profile not found")

    q = select(TrainingEnrollment).where(TrainingEnrollment.module_id == module_id)
    if payload.only_pending:
        q = q.where(TrainingEnrollment.status != EnrollmentStatus.completed)
    enrollments = db.execute(q).scalars().all()
    if not enrollments:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No one to email — assign the module first.")

    # Prefer the live public tunnel URL so links open for recipients; otherwise
    # fall back to the admin's current URL.
    from ..services.tunnel import detect_public_url

    base = (detect_public_url() or str(request.base_url)).rstrip("/")
    for e in enrollments:
        enqueue(db, "send_training_invite", {"enrollment_id": e.id, "profile_id": payload.profile_id, "base": base})
    db.commit()
    return Message(detail=f"Queued training emails to {len(enrollments)} recipient(s).")


# ── analytics ─────────────────────────────────────────────────────────────────
@router.get("/enrollments", response_model=list[EnrollmentOut])
def list_enrollments(module_id: int | None = None, db: DbSession = Depends(get_db)) -> list[EnrollmentOut]:
    q = (
        select(TrainingEnrollment, TrainingModule.title)
        .join(TrainingModule, TrainingModule.id == TrainingEnrollment.module_id)
        .order_by(TrainingEnrollment.id.desc())
    )
    if module_id is not None:
        q = q.where(TrainingEnrollment.module_id == module_id)
    rows = db.execute(q.limit(1000)).all()
    return [
        EnrollmentOut(
            id=e.id, module_id=e.module_id, module_title=title, email=e.email, token=e.token,
            status=e.status, score=e.score, attempts=e.attempts,
            assigned_at=e.assigned_at.isoformat(),
            completed_at=e.completed_at.isoformat() if e.completed_at else None,
        )
        for e, title in rows
    ]


@router.get("/leaderboard", response_model=list[LeaderboardRow])
def leaderboard(db: DbSession = Depends(get_db)) -> list[LeaderboardRow]:
    rows = db.execute(
        select(
            TrainingEnrollment.email,
            func.coalesce(func.sum(TrainingModule.points), 0).label("points"),
            func.count(TrainingEnrollment.id).label("completed"),
        )
        .join(TrainingModule, TrainingModule.id == TrainingEnrollment.module_id)
        .where(TrainingEnrollment.status == EnrollmentStatus.completed)
        .group_by(TrainingEnrollment.email)
        .order_by(func.sum(TrainingModule.points).desc())
        .limit(20)
    ).all()
    return [LeaderboardRow(email=r.email, points=int(r.points or 0), completed=int(r.completed)) for r in rows]


class RecommendationRow(BaseModel):
    email: str
    risk: str
    next_sim_difficulty: str
    recommended_training_difficulty: str
    targeted: int
    failed: int


@router.get("/recommendations", response_model=list[RecommendationRow])
def recommendations(db: DbSession = Depends(get_db)) -> list[RecommendationRow]:
    from ..services.adaptive import recommendations as _recs

    return [RecommendationRow(**r) for r in _recs(db)]


class AutoEnrollConfig(BaseModel):
    enabled: bool = False
    mode: str = "adaptive"  # adaptive | fixed
    module_id: int | None = None


@router.get("/auto-enroll", response_model=AutoEnrollConfig)
def get_auto_enroll(db: DbSession = Depends(get_db)) -> AutoEnrollConfig:
    from ..services.adaptive import get_auto_enroll_config

    return AutoEnrollConfig(**get_auto_enroll_config(db))


@router.put("/auto-enroll", response_model=AutoEnrollConfig, dependencies=[Depends(require_admin), Depends(csrf_protect)])
def put_auto_enroll(payload: AutoEnrollConfig, db: DbSession = Depends(get_db)) -> AutoEnrollConfig:
    from ..services.adaptive import get_auto_enroll_config, set_auto_enroll_config

    if payload.mode == "fixed" and payload.module_id is not None:
        if db.get(TrainingModule, payload.module_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Module not found")
    set_auto_enroll_config(db, enabled=payload.enabled, mode=payload.mode, module_id=payload.module_id)
    return AutoEnrollConfig(**get_auto_enroll_config(db))


@router.get("/summary", response_model=TrainingSummary)
def summary(db: DbSession = Depends(get_db)) -> TrainingSummary:
    modules = db.execute(select(func.count(TrainingModule.id))).scalar_one()
    total = db.execute(select(func.count(TrainingEnrollment.id))).scalar_one()
    completed = db.execute(
        select(func.count(TrainingEnrollment.id)).where(
            TrainingEnrollment.status == EnrollmentStatus.completed
        )
    ).scalar_one()
    rate = round(completed / total * 100) if total else 0
    return TrainingSummary(modules=modules, enrollments=total, completed=completed, completion_rate=rate)
