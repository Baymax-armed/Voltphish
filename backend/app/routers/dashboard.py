"""Aggregate stats for the dashboard overview (across all campaigns)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import (
    Campaign,
    CampaignStatus,
    Event,
    EventType,
    Group,
    LandingPage,
    Result,
    ResultStatus,
    SendingProfile,
    Template,
)

router = APIRouter(
    prefix="/api/v1/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)]
)


class CampaignCounts(BaseModel):
    total: int
    active: int
    completed: int
    draft: int
    scheduled: int


class Funnel(BaseModel):
    recipients: int
    sent: int
    opened: int
    clicked: int
    submitted: int
    reported: int
    trained: int
    error: int


class Counts(BaseModel):
    templates: int
    groups: int
    profiles: int
    pages: int


class DashboardOut(BaseModel):
    campaigns: CampaignCounts
    funnel: Funnel
    counts: Counts


@router.get("", response_model=DashboardOut)
def get_dashboard(db: DbSession = Depends(get_db)) -> DashboardOut:
    # Campaigns by status.
    status_rows = dict(
        db.execute(select(Campaign.status, func.count(Campaign.id)).group_by(Campaign.status)).all()
    )
    total_campaigns = sum(status_rows.values())

    # Results by status (aggregate funnel).
    res_rows = dict(
        db.execute(select(Result.status, func.count(Result.id)).group_by(Result.status)).all()
    )

    def rc(s: ResultStatus) -> int:
        return res_rows.get(s, 0)

    recipients = sum(res_rows.values())
    submitted = rc(ResultStatus.submitted)
    clicked = rc(ResultStatus.clicked) + submitted
    opened = rc(ResultStatus.opened) + clicked
    error = rc(ResultStatus.error)
    sent = recipients - rc(ResultStatus.scheduled) - rc(ResultStatus.sending) - error
    reported = rc(ResultStatus.reported)
    trained = db.execute(
        select(func.count(Result.id)).where(Result.trained_at.is_not(None))
    ).scalar_one()

    def cc(s: CampaignStatus) -> int:
        return status_rows.get(s, 0)

    return DashboardOut(
        campaigns=CampaignCounts(
            total=total_campaigns,
            active=cc(CampaignStatus.in_progress),
            completed=cc(CampaignStatus.completed),
            draft=cc(CampaignStatus.draft),
            scheduled=cc(CampaignStatus.scheduled),
        ),
        funnel=Funnel(
            recipients=recipients, sent=max(sent, 0), opened=opened, clicked=clicked,
            submitted=submitted, reported=reported, trained=trained, error=error,
        ),
        counts=Counts(
            templates=db.execute(select(func.count(Template.id))).scalar_one(),
            groups=db.execute(select(func.count(Group.id))).scalar_one(),
            profiles=db.execute(select(func.count(SendingProfile.id))).scalar_one(),
            pages=db.execute(select(func.count(LandingPage.id))).scalar_one(),
        ),
    )


class TimelinePoint(BaseModel):
    date: str
    sent: int
    opened: int
    clicked: int
    submitted: int


@router.get("/timeline", response_model=list[TimelinePoint])
def timeline(db: DbSession = Depends(get_db)) -> list[TimelinePoint]:
    """Engagement events per day across all campaigns (for the activity graph)."""
    day = func.date(Event.created_at)
    rows = db.execute(
        select(
            day.label("d"),
            func.sum(case((Event.type == EventType.email_sent, 1), else_=0)).label("sent"),
            func.sum(case((Event.type == EventType.email_opened, 1), else_=0)).label("opened"),
            func.sum(case((Event.type == EventType.clicked_link, 1), else_=0)).label("clicked"),
            func.sum(case((Event.type == EventType.submitted_data, 1), else_=0)).label("submitted"),
        )
        .group_by(day)
        .order_by(day)
    ).all()
    return [
        TimelinePoint(
            date=str(r.d), sent=int(r.sent or 0), opened=int(r.opened or 0),
            clicked=int(r.clicked or 0), submitted=int(r.submitted or 0),
        )
        for r in rows
    ]


class AtRiskUser(BaseModel):
    email: str
    clicked: int
    submitted: int
    total: int  # times targeted


@router.get("/at-risk", response_model=list[AtRiskUser])
def at_risk(db: DbSession = Depends(get_db)) -> list[AtRiskUser]:
    """Recipients who most often click / submit across all campaigns — i.e. who
    needs awareness training. Aggregated by email."""
    clicked = func.sum(
        case((Result.status.in_([ResultStatus.clicked, ResultStatus.submitted]), 1), else_=0)
    )
    submitted = func.sum(case((Result.status == ResultStatus.submitted, 1), else_=0))
    rows = db.execute(
        select(
            Result.email,
            clicked.label("clicked"),
            submitted.label("submitted"),
            func.count(Result.id).label("total"),
        )
        .group_by(Result.email)
        .having(clicked > 0)
        .order_by(submitted.desc(), clicked.desc())
        .limit(8)
    ).all()
    return [
        AtRiskUser(email=r.email, clicked=int(r.clicked or 0), submitted=int(r.submitted or 0), total=int(r.total))
        for r in rows
    ]


class Champion(BaseModel):
    email: str
    reported: int  # times they reported a simulated phish
    total: int     # times targeted


@router.get("/champions", response_model=list[Champion])
def champions(db: DbSession = Depends(get_db)) -> list[Champion]:
    """Security Champions — recipients who most often *report* a simulated phish
    (the desired behaviour). The positive counterpart to /at-risk; use it to
    recognise and reward good instincts. Aggregated by email."""
    reported = func.sum(case((Result.status == ResultStatus.reported, 1), else_=0))
    rows = db.execute(
        select(
            Result.email,
            reported.label("reported"),
            func.count(Result.id).label("total"),
        )
        .group_by(Result.email)
        .having(reported > 0)
        .order_by(reported.desc())
        .limit(8)
    ).all()
    return [
        Champion(email=r.email, reported=int(r.reported or 0), total=int(r.total))
        for r in rows
    ]


# ---- Human Risk Score ---------------------------------------------------------
# A per-person / per-department "human risk" index (0-100) derived from how each
# recipient behaves across simulations. Higher = riskier. Reporting the phish
# earns a bonus that lowers the score (good instinct).

_CONTRIB = {
    ResultStatus.submitted: 100,  # entered credentials — worst outcome
    ResultStatus.clicked: 70,     # followed the link
    ResultStatus.opened: 30,      # opened the mail
}


def _score(sum_contrib: float, targeted: int, reported: int) -> int:
    if targeted <= 0:
        return 0
    base = sum_contrib / targeted
    bonus = min(20.0, (reported / targeted) * 20.0)  # reporting lowers risk
    return max(0, min(100, round(base - bonus)))


def _level(score: int) -> str:
    if score >= 70:
        return "critical"
    if score >= 40:
        return "high"
    if score >= 15:
        return "medium"
    return "low"


class RiskUser(BaseModel):
    email: str
    department: str
    score: int
    level: str
    targeted: int
    clicked: int
    submitted: int
    reported: int


class RiskDept(BaseModel):
    name: str
    score: int
    level: str
    people: int


class RiskOut(BaseModel):
    overall_score: int
    overall_level: str
    total_people: int
    departments: list[RiskDept]
    top_users: list[RiskUser]


@router.get("/risk", response_model=RiskOut)
def risk(db: DbSession = Depends(get_db)) -> RiskOut:
    """Human Risk Score — behaviour-based risk index per user and department."""
    rows = db.execute(select(Result.email, Result.position, Result.status)).all()

    users: dict[str, dict] = {}
    for email, position, status in rows:
        u = users.setdefault(
            email,
            {"dept": None, "sum": 0.0, "targeted": 0, "clicked": 0, "submitted": 0, "reported": 0},
        )
        if position and not u["dept"]:
            u["dept"] = position
        u["targeted"] += 1
        u["sum"] += _CONTRIB.get(status, 0)
        if status in (ResultStatus.clicked, ResultStatus.submitted):
            u["clicked"] += 1
        if status == ResultStatus.submitted:
            u["submitted"] += 1
        if status == ResultStatus.reported:
            u["reported"] += 1

    user_out: list[RiskUser] = []
    dept_agg: dict[str, dict] = {}
    org_sum = org_count = 0.0
    for email, u in users.items():
        dept = u["dept"] or "Unassigned"
        score = _score(u["sum"], u["targeted"], u["reported"])
        user_out.append(
            RiskUser(
                email=email, department=dept, score=score, level=_level(score),
                targeted=u["targeted"], clicked=u["clicked"],
                submitted=u["submitted"], reported=u["reported"],
            )
        )
        d = dept_agg.setdefault(dept, {"sum": 0.0, "targeted": 0, "reported": 0, "people": 0})
        d["sum"] += u["sum"]
        d["targeted"] += u["targeted"]
        d["reported"] += u["reported"]
        d["people"] += 1
        org_sum += u["sum"]
        org_count += u["targeted"]

    departments = sorted(
        (
            RiskDept(
                name=name,
                score=_score(d["sum"], d["targeted"], d["reported"]),
                level=_level(_score(d["sum"], d["targeted"], d["reported"])),
                people=d["people"],
            )
            for name, d in dept_agg.items()
        ),
        key=lambda x: x.score,
        reverse=True,
    )
    top_users = sorted(user_out, key=lambda x: x.score, reverse=True)[:10]
    overall = _score(org_sum, int(org_count), sum(u["reported"] for u in users.values()))

    return RiskOut(
        overall_score=overall,
        overall_level=_level(overall),
        total_people=len(users),
        departments=departments,
        top_users=top_users,
    )
