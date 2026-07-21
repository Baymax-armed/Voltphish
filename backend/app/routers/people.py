"""People view (NG-021): every *recipient* (not operator) aggregated across all
campaigns into a risk profile — sims received, opened, clicked, submitted,
reported, and training completion. This is the cross-campaign 'who keeps
failing' view that drives remediation."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user
from ..models import EnrollmentStatus, Result, ResultStatus, TrainingEnrollment
from ..models.result import status_rank

router = APIRouter(
    prefix="/api/v1/people",
    tags=["people"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect)],
)


class PersonOut(BaseModel):
    email: str
    first_name: str | None
    last_name: str | None
    targeted: int          # sims received
    opened: int
    clicked: int           # clicked or submitted (a failure)
    submitted: int
    reported: int
    trainings_assigned: int
    trainings_completed: int
    last_activity: datetime | None
    risk: str              # high | medium | low


def _risk(targeted: int, clicked: int, submitted: int) -> str:
    fail_rate = (clicked / targeted) if targeted else 0.0
    if submitted > 0 or fail_rate >= 0.5:
        return "high"
    if clicked > 0:
        return "medium"
    return "low"


@router.get("", response_model=list[PersonOut])
def list_people(db: DbSession = Depends(get_db)) -> list[PersonOut]:
    # Aggregate every result row by lowercased email (people move between groups,
    # but the email is the stable identity). Cumulative funnel: a click also
    # counts as an open, a submit also counts as a click.
    agg: dict[str, dict] = {}
    rows = db.execute(
        select(
            Result.email, Result.first_name, Result.last_name,
            Result.status, Result.last_event_at,
        )
    ).all()
    for email, first, last, st, last_at in rows:
        if not email:
            continue
        key = email.strip().lower()
        p = agg.get(key)
        if p is None:
            p = agg[key] = {
                "email": key, "first_name": first, "last_name": last,
                "targeted": 0, "opened": 0, "clicked": 0, "submitted": 0,
                "reported": 0, "last_activity": None,
                "trainings_assigned": 0, "trainings_completed": 0,
            }
        # Keep a non-empty name if we have one.
        p["first_name"] = p["first_name"] or first
        p["last_name"] = p["last_name"] or last
        p["targeted"] += 1
        if status_rank(st) >= status_rank(ResultStatus.opened) and st != ResultStatus.error:
            p["opened"] += 1
        if st in (ResultStatus.clicked, ResultStatus.submitted):
            p["clicked"] += 1
        if st == ResultStatus.submitted:
            p["submitted"] += 1
        if st == ResultStatus.reported:
            p["reported"] += 1
        if last_at and (p["last_activity"] is None or last_at > p["last_activity"]):
            p["last_activity"] = last_at

    # Fold in training enrollment counts (assigned + completed) per email.
    tr = db.execute(
        select(TrainingEnrollment.email, TrainingEnrollment.status)
    ).all()
    for email, st in tr:
        if not email:
            continue
        p = agg.get(email.strip().lower())
        if p is None:
            continue  # only surface people who were actually targeted
        p["trainings_assigned"] += 1
        if st == EnrollmentStatus.completed:
            p["trainings_completed"] += 1

    out = [
        PersonOut(**p, risk=_risk(p["targeted"], p["clicked"], p["submitted"]))
        for p in agg.values()
    ]
    # Riskiest first, then most failures — a sensible default the UI can re-sort.
    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda r: (order[r.risk], -r.clicked, -r.targeted))
    return out
