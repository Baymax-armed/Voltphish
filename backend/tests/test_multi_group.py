"""NG-001: multiple target groups + exclusion/suppression, deduped."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import (
    Campaign,
    Group,
    Result,
    SendingProfile,
    Target,
    Template,
)
from app.services.audience import campaign_recipient_targets


def _seed() -> dict:
    """Two overlapping groups + an exclusion group. Returns ids + a profile/template."""
    db = SessionLocal()
    try:
        n = db.execute(select(func.count(Group.id))).scalar_one()
        sales = Group(name=f"mg-sales-{n}")
        support = Group(name=f"mg-support-{n}")
        execs = Group(name=f"mg-execs-{n}")
        tmpl = Template(name=f"mg-tmpl-{n}", subject="s", html="<p>x</p>")
        prof = SendingProfile(name=f"mg-prof-{n}", from_address="sec@example.com", kind="smtp", host="localhost")
        db.add_all([sales, support, execs, tmpl, prof]); db.flush()

        # sales: alice, bob ; support: BOB (dup, mixed case), carol ; execs: alice (excluded)
        db.add_all([
            Target(group_id=sales.id, email="alice@corp.com", first_name="Alice"),
            Target(group_id=sales.id, email="bob@corp.com"),
            Target(group_id=support.id, email="BOB@corp.com"),  # duplicate of bob
            Target(group_id=support.id, email="carol@corp.com"),
            Target(group_id=execs.id, email="alice@corp.com"),  # exclusion hits alice
        ])
        db.commit()
        return {
            "sales": sales.id, "support": support.id, "execs": execs.id,
            "tmpl": tmpl.id, "prof": prof.id,
        }
    finally:
        db.close()


def test_preview_dedupes_and_excludes(auth_client: TestClient) -> None:
    ids = _seed()
    # sales + support = {alice, bob, bob(dup), carol} -> unique {alice, bob, carol} = 3,
    # 1 duplicate collapsed. Exclude execs (alice) -> 2 final.
    r = auth_client.post("/api/v1/campaigns/preview-recipients", json={
        "group_ids": [ids["sales"], ids["support"]],
        "exclude_group_ids": [ids["execs"]],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"count": 2, "unique": 3, "excluded": 1, "duplicates": 1}


def test_create_multi_group_campaign_materializes_deduped(auth_client: TestClient) -> None:
    ids = _seed()
    r = auth_client.post("/api/v1/campaigns", json={
        "name": "MG combined", "template_id": ids["tmpl"], "profile_id": ids["prof"],
        "group_id": ids["sales"], "group_ids": [ids["sales"], ids["support"]],
        "exclude_group_ids": [ids["execs"]],
        "phish_url": "http://testserver/",
    })
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    db = SessionLocal()
    try:
        campaign = db.get(Campaign, cid)
        targets = campaign_recipient_targets(campaign)
        emails = sorted(t.email.lower() for t in targets)
        # alice excluded, bob deduped, carol kept.
        assert emails == ["bob@corp.com", "carol@corp.com"]
    finally:
        db.close()


def test_detail_exposes_group_ids_for_clone(auth_client: TestClient) -> None:
    ids = _seed()
    created = auth_client.post("/api/v1/campaigns", json={
        "name": "MG detail", "template_id": ids["tmpl"], "profile_id": ids["prof"],
        "group_id": ids["sales"], "group_ids": [ids["sales"], ids["support"]],
        "exclude_group_ids": [ids["execs"]], "phish_url": "http://testserver/",
    })
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    detail = auth_client.get(f"/api/v1/campaigns/{cid}").json()
    # A clone reads these back to reproduce the targeting.
    assert sorted(detail["target_group_ids"]) == sorted([ids["sales"], ids["support"]])
    assert detail["exclude_group_ids"] == [ids["execs"]]


def test_create_rejects_when_everyone_excluded(auth_client: TestClient) -> None:
    ids = _seed()
    # Target sales, exclude sales -> nobody left.
    r = auth_client.post("/api/v1/campaigns", json={
        "name": "MG empty", "template_id": ids["tmpl"], "profile_id": ids["prof"],
        "group_id": ids["sales"], "group_ids": [ids["sales"]],
        "exclude_group_ids": [ids["sales"]],
        "phish_url": "http://testserver/",
    })
    assert r.status_code == 400, r.text


def test_legacy_single_group_still_works(auth_client: TestClient) -> None:
    ids = _seed()
    # Old-style payload: only group_id, no group_ids/exclude.
    r = auth_client.post("/api/v1/campaigns", json={
        "name": "MG legacy", "template_id": ids["tmpl"], "profile_id": ids["prof"],
        "group_id": ids["support"], "phish_url": "http://testserver/",
    })
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, cid)
        emails = sorted(t.email.lower() for t in campaign_recipient_targets(campaign))
        assert emails == ["bob@corp.com", "carol@corp.com"]
    finally:
        db.close()
