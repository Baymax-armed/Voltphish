"""NG-010: send-time realism — business-hours shifting and jitter."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import (
    Campaign,
    CampaignStatus,
    Group,
    SendingProfile,
    Target,
    Template,
)
from app.services.sender import _shift_to_business_hours, enqueue_campaign


def test_business_hours_shift_weekend_and_night() -> None:
    tz = "Asia/Kolkata"
    z = ZoneInfo(tz)

    # A Sunday 03:00 local send → next Monday 09:00 local.
    sun_night = datetime(2026, 7, 19, 3, 0, tzinfo=z).astimezone(timezone.utc)  # 2026-07-19 is a Sunday
    out = _shift_to_business_hours(sun_night, tz).astimezone(z)
    assert out.weekday() == 0 and out.hour == 9  # Monday 09:00

    # A weekday 22:00 local → next day 09:00.
    wed_late = datetime(2026, 7, 22, 22, 0, tzinfo=z).astimezone(timezone.utc)  # Wed
    out2 = _shift_to_business_hours(wed_late, tz).astimezone(z)
    assert out2.weekday() == 3 and out2.hour == 9  # Thursday 09:00

    # Inside business hours → unchanged.
    wed_noon = datetime(2026, 7, 22, 12, 0, tzinfo=z).astimezone(timezone.utc)
    out3 = _shift_to_business_hours(wed_noon, tz).astimezone(z)
    assert out3.hour == 12 and out3.weekday() == 2


def _seed_campaign_with_targets(*, jitter: bool, business_hours: bool, tz: str, n_targets: int) -> int:
    db = SessionLocal()
    try:
        c = db.execute(select(func.count(Campaign.id))).scalar_one()
        tmpl = Template(name=f"sr-tmpl-{c}", subject="s", html="<p>x</p>")
        prof = SendingProfile(name=f"sr-prof-{c}", from_address="s@example.com", kind="smtp", host="localhost")
        grp = Group(name=f"sr-grp-{c}")
        db.add_all([tmpl, prof, grp]); db.flush()
        for i in range(n_targets):
            db.add(Target(group_id=grp.id, email=f"user{c}_{i}@corp.com"))
        # Drip window 10 hours out so business-hours shifting has room to move.
        camp = Campaign(
            name=f"SR {c}", status=CampaignStatus.scheduled,
            template_id=tmpl.id, group_id=grp.id, phish_url="http://x/c",
            send_by_at=datetime.now(timezone.utc) + timedelta(hours=10),
            send_jitter=jitter, business_hours_only=business_hours, send_timezone=tz,
        )
        camp.target_groups = [grp]
        db.add(camp); db.commit()
        return camp.id
    finally:
        db.close()


def test_enqueue_business_hours_lands_all_in_window() -> None:
    from app.models import Job

    cid = _seed_campaign_with_targets(jitter=True, business_hours=True, tz="Asia/Kolkata", n_targets=8)
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, cid)
        enqueue_campaign(db, campaign)
        db.commit()
        jobs = db.execute(
            select(Job).where(Job.type == "send_email").order_by(Job.id.desc()).limit(8)
        ).scalars().all()
        assert len(jobs) == 8
        z = ZoneInfo("Asia/Kolkata")
        for j in jobs:
            local = j.run_after.astimezone(z)
            assert local.weekday() < 5, f"weekend send: {local}"
            assert 9 <= local.hour < 17, f"out-of-hours send: {local}"
    finally:
        db.close()
