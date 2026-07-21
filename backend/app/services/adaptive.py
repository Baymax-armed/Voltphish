"""Adaptive training: just-in-time auto-enrollment + per-user difficulty.

When a recipient fails a simulation (clicks or submits), we can automatically
enroll them in a training module — the "teachable moment" auto-enrollment that
commercial SAT platforms are known for. In *adaptive* mode the module's
difficulty is chosen from the person's behaviour: someone who entered credentials
or repeatedly fails gets foundational material; a one-off clicker gets the next
step up. A recommendations view also suggests each user's next *simulation*
difficulty (savvy users earn harder lures; risky users get gentler ones).
"""
from __future__ import annotations

import logging
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..models import (
    Difficulty,
    EnrollmentStatus,
    Result,
    ResultStatus,
    Setting,
    TrainingEnrollment,
    TrainingModule,
)
from ..models.base import utcnow

log = logging.getLogger("voltphish.adaptive")

_K_ENABLED = "train_autoenroll_enabled"
_K_MODE = "train_autoenroll_mode"       # adaptive | fixed
_K_MODULE = "train_autoenroll_module_id"


def _g(db: DbSession, key: str, default: str = "") -> str:
    row = db.get(Setting, key)
    return row.value if row is not None and row.value not in (None, "") else default


def get_auto_enroll_config(db: DbSession) -> dict:
    mid = _g(db, _K_MODULE, "")
    return {
        "enabled": _g(db, _K_ENABLED, "0") == "1",
        "mode": _g(db, _K_MODE, "adaptive") or "adaptive",
        "module_id": int(mid) if mid.isdigit() else None,
    }


def _fail_count(db: DbSession, email: str) -> int:
    return db.execute(
        select(func.count(Result.id)).where(
            func.lower(Result.email) == email.lower(),
            Result.status.in_([ResultStatus.clicked, ResultStatus.submitted]),
        )
    ).scalar_one()


def _pick_difficulty(db: DbSession, email: str, trigger: str) -> Difficulty:
    """Map the failure to a training depth. Submitting credentials or repeat
    failures → foundational; a first-time click → one step up."""
    if _fail_count(db, email) >= 3:
        return Difficulty.beginner
    if trigger == "submitted":
        return Difficulty.beginner
    return Difficulty.intermediate


def _module_for_difficulty(db: DbSession, difficulty: Difficulty) -> TrainingModule | None:
    # Prefer a published module at the target difficulty (Phishing first), else any published.
    q = (
        select(TrainingModule)
        .where(TrainingModule.is_published.is_(True), TrainingModule.difficulty == difficulty)
        .order_by(TrainingModule.category != "Phishing", TrainingModule.id)
    )
    m = db.execute(q).scalars().first()
    if m is not None:
        return m
    return db.execute(
        select(TrainingModule).where(TrainingModule.is_published.is_(True)).order_by(TrainingModule.id)
    ).scalars().first()


def auto_enroll_on_fail(db: DbSession, *, result: Result, campaign_id: int, trigger: str) -> None:
    """Enroll a failing recipient in a training module if auto-enroll is on.
    Idempotent per (module, email): skips if an open enrollment already exists.
    Never raises — a training hiccup must not break tracking."""
    try:
        cfg = get_auto_enroll_config(db)
        if not cfg["enabled"] or not result.email:
            return
        if cfg["mode"] == "fixed" and cfg["module_id"]:
            module = db.get(TrainingModule, cfg["module_id"])
        else:
            module = _module_for_difficulty(db, _pick_difficulty(db, result.email, trigger))
        if module is None:
            return
        # One auto-enrollment per (recipient, campaign): the first failure event
        # wins, so a click-then-submit doesn't stack two modules on one person.
        existing = db.execute(
            select(TrainingEnrollment.id).where(
                func.lower(TrainingEnrollment.email) == result.email.lower(),
                TrainingEnrollment.campaign_id == campaign_id,
            )
        ).first()
        if existing:
            return
        db.add(
            TrainingEnrollment(
                module_id=module.id, email=result.email.lower(),
                token=secrets.token_urlsafe(24), campaign_id=campaign_id,
            )
        )
        db.commit()
        log.info("auto-enrolled %s in module %s (%s)", result.email, module.id, trigger)
    except Exception:  # noqa: BLE001
        log.exception("auto-enroll failed")
        db.rollback()


# ── adaptive next-simulation difficulty recommendations ───────────────────────
def recommendations(db: DbSession, limit: int = 50) -> list[dict]:
    """Per-recipient recommendation for their next simulation difficulty and the
    training depth they'd benefit from, derived from behaviour across campaigns."""
    rows = db.execute(select(Result.email, Result.status)).all()
    agg: dict[str, dict] = {}
    for email, status in rows:
        u = agg.setdefault(email, {"targeted": 0, "clicked": 0, "submitted": 0})
        u["targeted"] += 1
        if status in (ResultStatus.clicked, ResultStatus.submitted):
            u["clicked"] += 1
        if status == ResultStatus.submitted:
            u["submitted"] += 1

    out: list[dict] = []
    for email, u in agg.items():
        fail_rate = (u["clicked"] / u["targeted"]) if u["targeted"] else 0.0
        if u["submitted"] > 0 or fail_rate >= 0.5:
            risk, next_sim, train = "high", "beginner", "beginner"
        elif fail_rate > 0:
            risk, next_sim, train = "medium", "intermediate", "intermediate"
        else:
            risk, next_sim, train = "low", "advanced", "advanced"
        out.append({
            "email": email, "risk": risk, "next_sim_difficulty": next_sim,
            "recommended_training_difficulty": train,
            "targeted": u["targeted"], "failed": u["clicked"],
        })
    # Riskiest first.
    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda r: (order[r["risk"]], -r["failed"]))
    return out[:limit]


def set_auto_enroll_config(db: DbSession, *, enabled: bool, mode: str, module_id: int | None) -> None:
    def s(key: str, value: str | None) -> None:
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value, modified_at=utcnow()))
        else:
            row.value = value
            row.modified_at = utcnow()

    s(_K_ENABLED, "1" if enabled else "0")
    s(_K_MODE, "fixed" if mode == "fixed" else "adaptive")
    s(_K_MODULE, str(module_id) if module_id else "")
    db.commit()
