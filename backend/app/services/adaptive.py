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
from .queue import enqueue

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

    A per-campaign rule (NG-013) takes precedence: each campaign can pick its
    own trigger (clicked vs submitted-only), a fixed module (or adaptive), and
    whether to auto-email the training link. If no per-campaign rule is set, the
    global adaptive setting applies (backwards compatible).

    Idempotent per (recipient, campaign): the first failure event wins, so a
    click-then-submit doesn't stack two modules on one person. Never raises — a
    training hiccup must not break tracking."""
    from ..models import Campaign

    try:
        if not result.email:
            return

        campaign = db.get(Campaign, campaign_id)
        module: TrainingModule | None = None
        want_email = False

        ce_trigger = getattr(campaign, "auto_enroll_trigger", "off") if campaign else "off"
        if ce_trigger and ce_trigger != "off":
            # A submitted-only rule ignores plain clicks; a clicked rule fires on
            # either (a submit is also a click).
            if ce_trigger == "submitted" and trigger != "submitted":
                return
            if campaign.auto_enroll_module_id:
                module = db.get(TrainingModule, campaign.auto_enroll_module_id)
            if module is None:
                module = _module_for_difficulty(db, _pick_difficulty(db, result.email, trigger))
            want_email = bool(campaign.auto_enroll_email)
        else:
            cfg = get_auto_enroll_config(db)
            if not cfg["enabled"]:
                return
            if cfg["mode"] == "fixed" and cfg["module_id"]:
                module = db.get(TrainingModule, cfg["module_id"])
            else:
                module = _module_for_difficulty(db, _pick_difficulty(db, result.email, trigger))

        if module is None:
            return

        existing = db.execute(
            select(TrainingEnrollment.id).where(
                func.lower(TrainingEnrollment.email) == result.email.lower(),
                TrainingEnrollment.campaign_id == campaign_id,
            )
        ).first()
        if existing:
            return

        enrollment = TrainingEnrollment(
            module_id=module.id, email=result.email.lower(),
            token=secrets.token_urlsafe(24), campaign_id=campaign_id,
        )
        db.add(enrollment)
        db.commit()
        log.info(
            "auto-enrolled %s in module %s (campaign %s, %s)",
            result.email, module.id, campaign_id, trigger,
        )

        # Optionally deliver the training link straight away, via the campaign's
        # sending profile, through the durable job queue (restart-safe). Use the
        # live public URL (tunnel) so the link opens for the recipient, not a
        # localhost address only the server can reach.
        if want_email and campaign and campaign.profile_id:
            from .tunnel import resolve_public_base_url

            base = resolve_public_base_url().rstrip("/")
            enqueue(
                db, "send_training_invite",
                {"enrollment_id": enrollment.id, "profile_id": campaign.profile_id, "base": base},
            )
            db.commit()
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
