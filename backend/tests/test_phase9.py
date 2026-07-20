"""Phase 9: SMS (smishing) channel — console provider + short-link tracking."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient


def test_sms_profile_console_and_test(auth_client: TestClient) -> None:
    p = auth_client.post(
        "/api/v1/sms-profiles",
        json={"name": "Console SMS", "provider": "console", "from_number": "PhishSim"},
    )
    assert p.status_code == 201, p.text
    pid = p.json()["id"]
    assert auth_client.post(f"/api/v1/sms-profiles/{pid}/verify").status_code == 200
    sent = auth_client.post(
        f"/api/v1/sms-profiles/{pid}/test", json={"to": "+15551234567", "message": "hello"}
    )
    assert sent.status_code == 200
    assert "outbox" in sent.json()["detail"]


def test_sms_template_requires_text(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/v1/templates",
        json={"name": "bad sms", "channel": "sms", "html": "<p>x</p>"},  # no text
    )
    assert r.status_code == 422


def test_generic_sms_profile_needs_valid_json(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/v1/sms-profiles",
        json={"name": "bad generic", "provider": "generic", "config": "not-json"},
    )
    assert r.status_code == 422


def test_full_sms_campaign_and_short_link(auth_client: TestClient) -> None:
    prof = auth_client.post(
        "/api/v1/sms-profiles", json={"name": "Con2", "provider": "console"}
    ).json()
    tpl = auth_client.post(
        "/api/v1/templates",
        json={"name": "sms tpl", "channel": "sms", "text": "Hi {{.FirstName}}, verify: {{.URL}}"},
    ).json()
    grp = auth_client.post(
        "/api/v1/groups",
        json={"name": "sms grp", "targets": [{"email": "a@e.com", "phone": "+15550001111", "first_name": "Ann"}]},
    ).json()

    camp = auth_client.post(
        "/api/v1/campaigns",
        json={
            "name": "sms camp", "channel": "sms", "template_id": tpl["id"],
            "sms_profile_id": prof["id"], "group_id": grp["id"], "phish_url": "http://testserver",
        },
    )
    assert camp.status_code == 201, camp.text
    cid = camp.json()["id"]
    assert camp.json()["channel"] == "sms"

    auth_client.post(f"/api/v1/campaigns/{cid}/launch")
    detail = None
    for _ in range(50):
        detail = auth_client.get(f"/api/v1/campaigns/{cid}").json()
        if detail["stats"]["sent"] >= 1:
            break
        time.sleep(0.1)
    assert detail["stats"]["sent"] == 1

    r0 = detail["results"][0]
    assert r0["phone"] == "+15550001111"
    code = r0["short_code"]
    assert code

    # Hitting the short link records a click, like /c/{rid}.
    click = auth_client.get(f"/s/{code}", follow_redirects=False)
    assert click.status_code == 302
    stats = auth_client.get(f"/api/v1/campaigns/{cid}").json()["stats"]
    assert stats["clicked"] >= 1


def test_sms_campaign_needs_phone_targets(auth_client: TestClient) -> None:
    prof = auth_client.post("/api/v1/sms-profiles", json={"name": "Con3", "provider": "console"}).json()
    tpl = auth_client.post(
        "/api/v1/templates", json={"name": "sms tpl2", "channel": "sms", "text": "hi {{.URL}}"}
    ).json()
    grp = auth_client.post(
        "/api/v1/groups", json={"name": "no phone grp", "targets": [{"email": "b@e.com", "first_name": "B"}]}
    ).json()
    r = auth_client.post(
        "/api/v1/campaigns",
        json={"name": "sms nophone", "channel": "sms", "template_id": tpl["id"],
              "sms_profile_id": prof["id"], "group_id": grp["id"], "phish_url": "http://testserver"},
    )
    assert r.status_code == 400
    assert "phone" in r.json()["detail"]
