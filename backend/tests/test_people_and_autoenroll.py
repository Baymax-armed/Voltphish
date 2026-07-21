"""NG-013 (per-campaign auto-enroll on failure) and NG-021 (People risk view)."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

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
from app.services.adaptive import auto_enroll_on_fail


def _mk_campaign(db, *, trigger: str, module_id: int | None, tag: str) -> int:
    n = db.execute(select(func.count(Campaign.id))).scalar_one()
    t = Template(name=f"ae-tmpl-{n}", subject="s", html="<p>x</p>")
    g = Group(name=f"ae-grp-{n}")
    db.add_all([t, g]); db.flush()
    c = Campaign(
        name=f"AE {tag} {n}", status=CampaignStatus.in_progress,
        template_id=t.id, group_id=g.id, phish_url="http://x/c",
        auto_enroll_trigger=trigger, auto_enroll_module_id=module_id, auto_enroll_email=False,
    )
    db.add(c); db.commit()
    return c.id


def _enrollments(db, campaign_id: int) -> list[TrainingEnrollment]:
    return list(db.execute(
        select(TrainingEnrollment).where(TrainingEnrollment.campaign_id == campaign_id)
    ).scalars().all())


def test_autoenroll_submitted_only_ignores_clicks() -> None:
    db = SessionLocal()
    try:
        mod = TrainingModule(title="AE submitted mod", category="Phishing"); db.add(mod); db.commit()
        cid = _mk_campaign(db, trigger="submitted", module_id=mod.id, tag="sub")
        r = Result(campaign_id=cid, rid="ae-sub-1", email="Clicker@corp.com", status=ResultStatus.clicked)
        db.add(r); db.commit()

        # A plain click must NOT enrol under a submitted-only rule.
        auto_enroll_on_fail(db, result=r, campaign_id=cid, trigger="clicked")
        assert _enrollments(db, cid) == []

        # A submit does enrol, into the chosen module, tagged to the campaign.
        auto_enroll_on_fail(db, result=r, campaign_id=cid, trigger="submitted")
        enr = _enrollments(db, cid)
        assert len(enr) == 1
        assert enr[0].module_id == mod.id
        assert enr[0].email == "clicker@corp.com"  # lowercased

        # Idempotent: a second failure event doesn't stack a duplicate.
        auto_enroll_on_fail(db, result=r, campaign_id=cid, trigger="submitted")
        assert len(_enrollments(db, cid)) == 1
    finally:
        db.close()


def test_autoenroll_clicked_trigger_fires_on_click() -> None:
    db = SessionLocal()
    try:
        mod = TrainingModule(title="AE clicked mod", category="Phishing"); db.add(mod); db.commit()
        cid = _mk_campaign(db, trigger="clicked", module_id=mod.id, tag="clk")
        r = Result(campaign_id=cid, rid="ae-clk-1", email="bob@corp.com", status=ResultStatus.clicked)
        db.add(r); db.commit()

        auto_enroll_on_fail(db, result=r, campaign_id=cid, trigger="clicked")
        enr = _enrollments(db, cid)
        assert len(enr) == 1 and enr[0].module_id == mod.id
    finally:
        db.close()


def test_autoenroll_off_does_nothing() -> None:
    db = SessionLocal()
    try:
        cid = _mk_campaign(db, trigger="off", module_id=None, tag="off")
        r = Result(campaign_id=cid, rid="ae-off-1", email="carol@corp.com", status=ResultStatus.submitted)
        db.add(r); db.commit()
        auto_enroll_on_fail(db, result=r, campaign_id=cid, trigger="submitted")
        # Global auto-enroll is off by default in tests, so nothing happens.
        assert _enrollments(db, cid) == []
    finally:
        db.close()


def test_create_campaign_rejects_bad_autoenroll_module(auth_client: TestClient) -> None:
    from app.models import SendingProfile

    # A group needs at least one target for a campaign to be creatable.
    db = SessionLocal()
    try:
        from app.models import Target

        n = db.execute(select(func.count(Campaign.id))).scalar_one()
        t = Template(name=f"aebad-tmpl-{n}", subject="s", html="<p>x</p>")
        g = Group(name=f"aebad-grp-{n}")
        prof = SendingProfile(name=f"aebad-prof-{n}", from_address="sec@example.com", kind="smtp", host="localhost")
        db.add_all([t, g, prof]); db.flush()
        db.add(Target(group_id=g.id, email="someone@corp.com"))
        db.commit()
        tid, gid, pid = t.id, g.id, prof.id
    finally:
        db.close()

    r = auth_client.post("/api/v1/campaigns", json={
        "name": "AE bad module", "template_id": tid, "group_id": gid, "profile_id": pid,
        "phish_url": "http://testserver/", "auto_enroll_trigger": "submitted",
        "auto_enroll_module_id": 999999,
    })
    assert r.status_code == 400, r.text


def test_people_aggregates_and_risk(auth_client: TestClient) -> None:
    db = SessionLocal()
    try:
        n = db.execute(select(func.count(Campaign.id))).scalar_one()
        t = Template(name=f"ppl-tmpl-{n}", subject="s", html="<p>x</p>")
        g = Group(name=f"ppl-grp-{n}")
        db.add_all([t, g]); db.flush()
        c = Campaign(name=f"People QA {n}", status=CampaignStatus.in_progress,
                     template_id=t.id, group_id=g.id, phish_url="http://x/c")
        db.add(c); db.flush()
        # danger@ submits (high), safe@ only opens (low).
        db.add_all([
            Result(campaign_id=c.id, rid=f"ppl-{n}-1", email="Danger@corp.com",
                   first_name="Dan", status=ResultStatus.submitted),
            Result(campaign_id=c.id, rid=f"ppl-{n}-2", email="safe@corp.com",
                   status=ResultStatus.opened),
        ])
        db.flush()
        # danger@ was assigned + completed a module.
        mod = TrainingModule(title=f"ppl-mod-{n}", category="Phishing"); db.add(mod); db.flush()
        db.add(TrainingEnrollment(module_id=mod.id, email="danger@corp.com",
                                  token=f"ppl-tok-{n}", status=EnrollmentStatus.completed))
        db.commit()
    finally:
        db.close()

    people = auth_client.get("/api/v1/people").json()
    by_email = {p["email"]: p for p in people}
    assert "danger@corp.com" in by_email and "safe@corp.com" in by_email

    dan = by_email["danger@corp.com"]
    assert dan["risk"] == "high"
    assert dan["submitted"] >= 1 and dan["clicked"] >= 1  # submit counts as a click
    assert dan["trainings_completed"] >= 1

    safe = by_email["safe@corp.com"]
    assert safe["risk"] == "low"
    assert safe["clicked"] == 0 and safe["opened"] >= 1
