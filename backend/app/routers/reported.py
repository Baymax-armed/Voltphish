"""Admin triage of employee-reported emails + Report-Phish add-in config."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user
from ..permissions import require_permission

require_admin = require_permission("reported:view")
from ..models import ReportedEmail, ReportStatus
from ..schemas.common import Message
from ..services.report_token import get_or_create_report_token, regenerate_report_token

router = APIRouter(
    prefix="/api/v1/reported", tags=["reported"], dependencies=[Depends(get_current_user)]
)


class ReportedOut(BaseModel):
    id: int
    reporter_email: str | None
    subject: str | None
    sender: str | None
    body_preview: str | None
    source: str
    is_simulation: bool
    matched_rid: str | None
    status: ReportStatus
    notes: str | None
    created_at: str

    model_config = {"from_attributes": True}


class ReportedSummary(BaseModel):
    total: int
    new: int
    simulations: int
    real: int


class StatusUpdate(BaseModel):
    status: ReportStatus | None = None
    notes: str | None = None


def _out(r: ReportedEmail) -> ReportedOut:
    return ReportedOut(
        id=r.id, reporter_email=r.reporter_email, subject=r.subject, sender=r.sender,
        body_preview=r.body_preview, source=r.source, is_simulation=r.is_simulation,
        matched_rid=r.matched_rid, status=r.status, notes=r.notes,
        created_at=r.created_at.isoformat(),
    )


@router.get("", response_model=list[ReportedOut])
def list_reported(
    only_real: bool = False,
    db: DbSession = Depends(get_db),
) -> list[ReportedOut]:
    q = select(ReportedEmail).order_by(ReportedEmail.id.desc())
    if only_real:
        q = q.where(ReportedEmail.is_simulation.is_(False))
    rows = db.execute(q.limit(500)).scalars().all()
    return [_out(r) for r in rows]


@router.get("/summary", response_model=ReportedSummary)
def summary(db: DbSession = Depends(get_db)) -> ReportedSummary:
    total = db.execute(select(func.count(ReportedEmail.id))).scalar_one()
    new = db.execute(
        select(func.count(ReportedEmail.id)).where(ReportedEmail.status == ReportStatus.new)
    ).scalar_one()
    sims = db.execute(
        select(func.count(ReportedEmail.id)).where(ReportedEmail.is_simulation.is_(True))
    ).scalar_one()
    return ReportedSummary(total=total, new=new, simulations=sims, real=total - sims)


@router.patch("/{report_id}", response_model=ReportedOut, dependencies=[Depends(csrf_protect)])
def update_reported(
    report_id: int,
    payload: StatusUpdate,
    db: DbSession = Depends(get_db),
) -> ReportedOut:
    row = db.get(ReportedEmail, report_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if payload.status is not None:
        row.status = payload.status
    if payload.notes is not None:
        row.notes = payload.notes[:5000]
    db.commit()
    return _out(row)


@router.delete("/{report_id}", response_model=Message, dependencies=[Depends(csrf_protect)])
def delete_reported(report_id: int, db: DbSession = Depends(get_db)) -> Message:
    row = db.get(ReportedEmail, report_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return Message(detail="Deleted")


# ── Add-in config (admin) ─────────────────────────────────────────────────────
class AddinConfig(BaseModel):
    token: str
    manifest_url: str
    taskpane_url: str
    gmail_script_url: str


@router.get("/addin/config", response_model=AddinConfig, dependencies=[Depends(require_admin)])
def addin_config(db: DbSession = Depends(get_db)) -> AddinConfig:
    token = get_or_create_report_token(db)
    return AddinConfig(
        token=token,
        manifest_url="/addins/outlook/manifest.xml",
        taskpane_url="/addins/outlook/taskpane.html",
        gmail_script_url="/addins/gmail/Code.gs",
    )


@router.post("/addin/regenerate", response_model=AddinConfig, dependencies=[Depends(require_admin), Depends(csrf_protect)])
def addin_regenerate(db: DbSession = Depends(get_db)) -> AddinConfig:
    token = regenerate_report_token(db)
    return AddinConfig(
        token=token,
        manifest_url="/addins/outlook/manifest.xml",
        taskpane_url="/addins/outlook/taskpane.html",
        gmail_script_url="/addins/gmail/Code.gs",
    )
