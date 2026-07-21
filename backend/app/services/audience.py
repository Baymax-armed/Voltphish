"""Campaign-outcome → audience selection, shared by the training remediation
loop (enrol failers) and 'save as group' (build a reusable re-test list).

Single source of truth for the outcome→who mapping so the two features can't
drift apart. 'clicked' deliberately includes submitters — someone who entered
data on the fake page also clicked the link, and both are failures worth
remediating."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import Result, ResultStatus

# outcome value → allowed labels shown in the UI (Training.tsx TRAINING_OUTCOMES).
OUTCOMES = ("all", "clicked", "submitted", "opened", "reported", "no_action")


def outcome_filter(outcome: str):
    """A SQLAlchemy filter expression for the given outcome, or None for 'all'
    (and for any unknown value, which is treated as 'all')."""
    return {
        "all": None,
        "clicked": Result.status.in_([ResultStatus.clicked, ResultStatus.submitted]),
        "submitted": Result.status == ResultStatus.submitted,
        "opened": Result.status == ResultStatus.opened,
        "reported": Result.status == ResultStatus.reported,
        "no_action": Result.status.in_(
            [ResultStatus.sent, ResultStatus.scheduled, ResultStatus.sending, ResultStatus.error]
        ),
    }.get(outcome, None)


def campaign_results(db: DbSession, campaign_id: int, outcome: str) -> list[Result]:
    """Result rows for a campaign matching the outcome (for name snapshots)."""
    q = select(Result).where(Result.campaign_id == campaign_id)
    f = outcome_filter(outcome)
    if outcome != "all" and f is not None:
        q = q.where(f)
    return list(db.execute(q).scalars().all())


def campaign_emails(db: DbSession, campaign_id: int, outcome: str) -> set[str]:
    """Unique, lowercased recipient emails for a campaign+outcome."""
    return {r.email.strip().lower() for r in campaign_results(db, campaign_id, outcome) if r.email}
