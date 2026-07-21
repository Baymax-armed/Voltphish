"""VP-010/011/012 — training remediation loop: enrol a campaign's audience
filtered by outcome, with a live count preview. Verifies the outcome→who
mapping and the dedupe/skip behaviour of assignment."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.models import (
    Campaign,
    CampaignStatus,
    EnrollmentStatus,
    Group,
    Result,
    ResultStatus,
    Template,
    TrainingEnrollment,
    TrainingModule,
)


def _seed_campaign() -> tuple[int, int]:
    """Create a campaign whose recipients span every outcome, plus a module.
    Returns (campaign_id, module_id)."""
    db = SessionLocal()
    try:
        # Unique suffix so repeated fixture use doesn't collide on unique names.
        from sqlalchemy import func

        n = db.execute(select(func.count(Campaign.id))).scalar_one()
        tmpl = Template(name=f"aud-tmpl-{n}", subject="s", html="<p>x</p>")
        grp = Group(name=f"aud-grp-{n}")
        db.add_all([tmpl, grp])
        db.flush()
        camp = Campaign(
            name=f"Audience QA campaign {n}",
            status=CampaignStatus.in_progress,
            template_id=tmpl.id,
            group_id=grp.id,
            phish_url="http://testserver/c",
        )
        db.add(camp)
        db.flush()

        # One recipient per outcome (emails deliberately mixed-case to prove
        # the endpoint lowercases/dedupes).
        rows = [
            ("Alice@corp.com", ResultStatus.submitted),
            ("bob@corp.com", ResultStatus.clicked),
            ("carol@corp.com", ResultStatus.opened),
            ("dave@corp.com", ResultStatus.reported),
            ("erin@corp.com", ResultStatus.sent),
            ("frank@corp.com", ResultStatus.error),
        ]
        for i, (email, st) in enumerate(rows):
            db.add(Result(campaign_id=camp.id, rid=f"aud-rid-{n}-{i}", email=email, status=st))

        mod = TrainingModule(title=f"Remediation 101 ({n})", description=None, category="General")
        db.add(mod)
        db.commit()
        return camp.id, mod.id
    finally:
        db.close()


@pytest.fixture
def seeded() -> tuple[int, int]:
    return _seed_campaign()


def test_audience_counts_by_outcome(auth_client: TestClient, seeded: tuple[int, int]) -> None:
    cid, _ = seeded

    def count(outcome: str) -> tuple[int, int]:
        r = auth_client.post("/api/v1/training/audience", json={"campaign_id": cid, "outcome": outcome})
        assert r.status_code == 200, r.text
        body = r.json()
        return body["count"], body["total"]

    # 6 recipients total regardless of filter.
    assert count("all") == (6, 6)
    # "clicked" includes submitters (they clicked and went further): bob + alice.
    assert count("clicked")[0] == 2
    # "submitted" is only the worst case: alice.
    assert count("submitted")[0] == 1
    # "opened" only: carol (clicked/submitted are past 'opened').
    assert count("opened")[0] == 1
    # "reported": dave.
    assert count("reported")[0] == 1
    # "no_action" = sent/scheduled/sending/error: erin + frank.
    assert count("no_action")[0] == 2


def test_assign_by_campaign_outcome_dedupes(auth_client: TestClient, seeded: tuple[int, int]) -> None:
    cid, mid = seeded

    # Enrol everyone who clicked (incl. submitters): alice + bob → 2.
    r = auth_client.post(
        f"/api/v1/training/modules/{mid}/assign",
        json={"campaign_id": cid, "outcome": "clicked"},
    )
    assert r.status_code == 200, r.text
    assert "2" in r.json()["detail"]

    db = SessionLocal()
    try:
        emails = {
            e.email
            for e in db.query(TrainingEnrollment).filter(TrainingEnrollment.module_id == mid).all()
        }
        # Lowercased + only the two who clicked/submitted.
        assert emails == {"alice@corp.com", "bob@corp.com"}
    finally:
        db.close()

    # Re-assigning the same audience creates nobody new (open enrolments skipped).
    r2 = auth_client.post(
        f"/api/v1/training/modules/{mid}/assign",
        json={"campaign_id": cid, "outcome": "clicked"},
    )
    assert r2.status_code == 200, r2.text
    assert "0" in r2.json()["detail"]


def test_save_audience_as_group(auth_client: TestClient, seeded: tuple[int, int]) -> None:
    cid, _ = seeded

    # Save everyone who clicked (incl. submitters) as a reusable group.
    r = auth_client.post(
        f"/api/v1/campaigns/{cid}/save-group",
        json={"name": "QA clickers retest", "outcome": "clicked"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["added"] == 2  # alice (submitted) + bob (clicked)

    # The group is real and contains exactly those two, lowercased.
    groups = auth_client.get("/api/v1/groups").json()
    grp = next(g for g in groups if g["id"] == body["group_id"])
    assert grp["target_count"] == 2

    # Duplicate name is rejected, not silently merged.
    dup = auth_client.post(
        f"/api/v1/campaigns/{cid}/save-group",
        json={"name": "QA clickers retest", "outcome": "clicked"},
    )
    assert dup.status_code == 409, dup.text

    # A different outcome makes a different group (no_action = erin + frank).
    other = auth_client.post(
        f"/api/v1/campaigns/{cid}/save-group",
        json={"name": "QA no-action", "outcome": "no_action"},
    )
    assert other.status_code == 201, other.text
    assert other.json()["added"] == 2


def test_assign_requires_recipients(auth_client: TestClient, seeded: tuple[int, int]) -> None:
    cid, mid = seeded
    # "reported" is a single recipient here, but pair an empty email list with a
    # campaign that has nobody in that outcome to prove the guard fires.
    empty_db = SessionLocal()
    try:
        empty = Campaign(
            name="Empty QA campaign",
            status=CampaignStatus.in_progress,
            template_id=empty_db.query(Template).first().id,
            group_id=empty_db.query(Group).first().id,
            phish_url="http://testserver/c",
        )
        empty_db.add(empty)
        empty_db.commit()
        empty_id = empty.id
    finally:
        empty_db.close()

    r = auth_client.post(
        f"/api/v1/training/modules/{mid}/assign",
        json={"campaign_id": empty_id, "outcome": "clicked"},
    )
    assert r.status_code == 400
