"""Captured submitted-data view: when capture is enabled, ordinary field VALUES
are recorded and shown, but password/secret fields are NEVER stored."""
from __future__ import annotations

import json

from app.config import get_settings
from app.database import SessionLocal
from app.models import (
    Campaign,
    CampaignStatus,
    Group,
    Result,
    ResultStatus,
    SendingProfile,
    Template,
)


def _seed_clicked_result(rid: str) -> int:
    db = SessionLocal()
    try:
        tmpl = Template(name=f"cap-{rid}", subject="s", html="<p>x</p>")
        prof = SendingProfile(name=f"cap-{rid}", from_address="a@b.com", kind="smtp", host="h")
        grp = Group(name=f"cap-{rid}")
        db.add_all([tmpl, prof, grp])
        db.flush()
        camp = Campaign(
            name=f"Cap {rid}", status=CampaignStatus.in_progress,
            template_id=tmpl.id, group_id=grp.id, phish_url="http://testserver",
        )
        db.add(camp)
        db.flush()
        db.add(Result(
            rid=rid, short_code=rid[-6:], email="victim@corp.com",
            status=ResultStatus.clicked, campaign_id=camp.id,
        ))
        db.commit()
        return camp.id
    finally:
        db.close()


def test_full_capture_stores_all_fields_including_password(auth_client):
    """FULL CAPTURE (opt-in): every submitted field is stored, incl. the password."""
    settings = get_settings()
    old = settings.capture_passwords
    settings.capture_passwords = True
    try:
        cid = _seed_clicked_result("caprid001")
        r = auth_client.post(
            "/p/caprid001",
            data={
                "username": "victim@corp.com",
                "comment": "please help",
                "password": "hunter2",
                "code": "999111",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303

        events = auth_client.get(f"/api/v1/campaigns/{cid}/events").json()
        subs = [e for e in events if e["type"] == "submitted_data" and e.get("details")]
        assert subs, "expected a submitted_data event carrying captured details"
        d = json.loads(subs[-1]["details"])

        # Everything the recipient submitted is stored, including credentials.
        assert d.get("username") == "victim@corp.com"
        assert d.get("comment") == "please help"
        assert d.get("password") == "hunter2"
        assert d.get("code") == "999111"
    finally:
        settings.capture_passwords = old


def test_no_capture_by_default(auth_client):
    """With capture off (default), no field values are stored — only the event."""
    settings = get_settings()
    old = settings.capture_passwords
    settings.capture_passwords = False
    try:
        cid = _seed_clicked_result("caprid002")
        r = auth_client.post(
            "/p/caprid002",
            data={"username": "victim@corp.com", "password": "hunter2"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        events = auth_client.get(f"/api/v1/campaigns/{cid}/events").json()
        subs = [e for e in events if e["type"] == "submitted_data"]
        assert subs, "submission should still be recorded as an event"
        assert all(not e.get("details") for e in subs), "no values should be stored when capture is off"
        assert "hunter2" not in str(events)
    finally:
        settings.capture_passwords = old
