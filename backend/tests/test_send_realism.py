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


def _seed_throttled_campaign(*, interval: int, n_targets: int) -> int:
    """An immediate-launch campaign (no drip window) with a fixed per-email
    pause of `interval` seconds."""
    db = SessionLocal()
    try:
        c = db.execute(select(func.count(Campaign.id))).scalar_one()
        tmpl = Template(name=f"th-tmpl-{c}", subject="s", html="<p>x</p>")
        prof = SendingProfile(name=f"th-prof-{c}", from_address="s@example.com", kind="smtp", host="localhost")
        grp = Group(name=f"th-grp-{c}")
        db.add_all([tmpl, prof, grp]); db.flush()
        for i in range(n_targets):
            db.add(Target(group_id=grp.id, email=f"thuser{c}_{i}@corp.com"))
        camp = Campaign(
            name=f"TH {c}", status=CampaignStatus.scheduled,
            template_id=tmpl.id, group_id=grp.id, phish_url="http://x/c",
            send_interval_seconds=interval,  # no send_by_at → immediate, throttled
        )
        camp.target_groups = [grp]
        db.add(camp); db.commit()
        return camp.id
    finally:
        db.close()


def test_send_interval_spaces_immediate_sends() -> None:
    """A per-email pause spaces run_after by exactly the interval, even with no
    drip window (immediate launch), so a burst can't trip the SMTP provider."""
    from app.models import Job

    cid = _seed_throttled_campaign(interval=5, n_targets=6)
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, cid)
        enqueue_campaign(db, campaign)
        db.commit()
        jobs = db.execute(
            select(Job).where(Job.type == "send_email").order_by(Job.id)
        ).scalars().all()[-6:]
        times = sorted(j.run_after for j in jobs)
        # Consecutive sends are 5s apart (first ≈ now, then +5, +10, …).
        for earlier, later in zip(times, times[1:]):
            gap = (later - earlier).total_seconds()
            assert abs(gap - 5) < 0.5, f"expected ~5s spacing, got {gap}s"
    finally:
        db.close()


def test_no_interval_no_spacing() -> None:
    """interval=0 (the default) => all sends fire immediately (no throttle)."""
    from app.models import Job

    cid = _seed_throttled_campaign(interval=0, n_targets=4)
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, cid)
        enqueue_campaign(db, campaign)
        db.commit()
        jobs = db.execute(
            select(Job).where(Job.type == "send_email").order_by(Job.id)
        ).scalars().all()[-4:]
        times = [j.run_after for j in jobs]
        # All within a hair of each other (queued "now").
        span = (max(times) - min(times)).total_seconds()
        assert span < 1.0, f"expected no spacing, got span {span}s"
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
