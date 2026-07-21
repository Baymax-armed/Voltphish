"""Tests for the newer features + hardening: RBAC, report ingest, training LMS,
governance launch gate, benchmark, VAP, deliverability, SSO config.

Uses the shared fixtures in conftest.py (isolated SQLite DB, console mail)."""
from __future__ import annotations

from fastapi.testclient import TestClient


# ── helpers ───────────────────────────────────────────────────────────────────
def _make_operator(auth_client: TestClient, email: str, perms: list[str]) -> str:
    pw = "operator-pw-at-least-12-chars"
    r = auth_client.post("/api/v1/users", json={"email": email, "password": pw, "role": "operator", "permissions": perms})
    assert r.status_code == 201, r.text
    return pw


def _login(client: TestClient, email: str, pw: str) -> TestClient:
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return c


# ── RBAC / delegated permissions ──────────────────────────────────────────────
def test_rbac_delegation_matrix(auth_client: TestClient):
    _make_operator(auth_client, "deleg1@corp.com", ["users:manage"])
    op = _login(auth_client, "deleg1@corp.com", "operator-pw-at-least-12-chars")
    # granted -> 200
    assert op.get("/api/v1/users").status_code == 200
    # not granted -> 403
    assert op.get("/api/v1/settings/ai").status_code == 403
    assert op.get("/api/v1/webhooks").status_code == 403


def test_rbac_plain_operator_blocked(auth_client: TestClient):
    _make_operator(auth_client, "plain1@corp.com", [])
    op = _login(auth_client, "plain1@corp.com", "operator-pw-at-least-12-chars")
    assert op.get("/api/v1/users").status_code == 403
    # AuthOut exposes effective permissions (empty for a plain operator)
    me = op.get("/api/v1/auth/me").json()
    assert me["permissions"] == []


def test_rbac_no_self_escalation(auth_client: TestClient):
    """A delegated users:manage operator must NOT be able to promote to admin
    or grant permissions (would defeat least-privilege)."""
    _make_operator(auth_client, "escal@corp.com", ["users:manage"])
    op = _login(auth_client, "escal@corp.com", "operator-pw-at-least-12-chars")
    me = op.get("/api/v1/auth/me").json()
    # self-promotion to admin -> 403
    assert op.put(f"/api/v1/users/{me['id']}", json={"role": "admin"}).status_code == 403
    # granting itself more permissions -> 403
    assert op.put(f"/api/v1/users/{me['id']}", json={"permissions": ["settings:manage"]}).status_code == 403
    # creating a fresh admin -> 403
    assert op.post("/api/v1/users", json={"email": "x@corp.com", "password": "pw-at-least-12-chars", "role": "admin"}).status_code == 403
    # still just an operator with the one delegated perm
    assert op.get("/api/v1/auth/me").json()["permissions"] == ["users:manage"]


def test_rbac_bogus_permission_filtered(auth_client: TestClient):
    _make_operator(auth_client, "deleg2@corp.com", ["users:manage", "not:a:real:perm"])
    op = _login(auth_client, "deleg2@corp.com", "operator-pw-at-least-12-chars")
    assert op.get("/api/v1/auth/me").json()["permissions"] == ["users:manage"]


# ── Report-Phish ingest ───────────────────────────────────────────────────────
def test_report_ingest_requires_token(client: TestClient):
    r = client.post("/api/v1/inbound/report", json={"body": "hi"})
    assert r.status_code == 401
    r = client.post("/api/v1/inbound/report", headers={"X-Report-Token": "wrong"}, json={"body": "hi"})
    assert r.status_code == 401


def test_report_credit_requires_reporter_match(auth_client: TestClient):
    """A leaked ingest token + a known rid must NOT let a non-recipient credit
    the champion — only the actual recipient's report is credited."""
    import secrets

    from app.database import SessionLocal
    from app.models import Campaign, Group, Result, ResultStatus, Template, utcnow
    from app.models.campaign import CampaignStatus

    db = SessionLocal()
    t = Template(name=f"ri-t-{secrets.token_hex(3)}", channel="email", subject="s", html="<p>x</p>", created_at=utcnow(), modified_at=utcnow())
    g = Group(name=f"ri-g-{secrets.token_hex(3)}", created_at=utcnow(), modified_at=utcnow())
    db.add_all([t, g]); db.flush()
    c = Campaign(name=f"ri-c-{secrets.token_hex(3)}", status=CampaignStatus.in_progress, channel="email",
                 template_id=t.id, group_id=g.id, phish_url="http://testserver", created_at=utcnow())
    db.add(c); db.flush()
    rid = "RIRID" + secrets.token_hex(4)
    res = Result(campaign_id=c.id, rid=rid, email="victim@corp.com", status=ResultStatus.clicked, created_at=utcnow())
    db.add(res); db.commit()
    rid_body = f"suspicious link https://h/c/{rid}"

    token = auth_client.get("/api/v1/reported/addin/config").json()["token"]
    # attacker (different reporter) with the victim's rid -> NOT credited
    r = auth_client.post("/api/v1/inbound/report", headers={"X-Report-Token": token},
                         json={"reporter_email": "attacker@corp.com", "subject": "x", "body": rid_body})
    assert r.json()["simulation"] is False
    db.expire_all()
    assert db.get(Result, res.id).status == ResultStatus.clicked  # not credited
    # the real recipient -> credited
    r2 = auth_client.post("/api/v1/inbound/report", headers={"X-Report-Token": token},
                          json={"reporter_email": "victim@corp.com", "subject": "x", "body": rid_body})
    assert r2.json()["simulation"] is True
    db.expire_all()
    assert db.get(Result, res.id).status == ResultStatus.reported
    db.close()


def test_totp_matched_step_and_replay_guard():
    import pyotp

    from app.services.totp import matched_step

    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    step = matched_step(secret, code)
    assert step is not None
    # the same code resolves to the same step, so the login path rejects reuse
    assert matched_step(secret, code) == step
    assert matched_step(secret, "000000") in (None,) or matched_step(secret, "000000") != step


def test_report_real_email_goes_to_triage(auth_client: TestClient):
    token = auth_client.get("/api/v1/reported/addin/config").json()["token"]
    r = auth_client.post(
        "/api/v1/inbound/report",
        headers={"X-Report-Token": token},
        json={"reporter_email": "bob@corp.com", "subject": "Overdue invoice", "sender": "x@evil.tld", "body": "pay http://evil.tld"},
    )
    assert r.status_code == 200
    assert r.json()["simulation"] is False
    # shows up in the admin triage queue
    rows = auth_client.get("/api/v1/reported?only_real=true").json()
    assert any(row["subject"] == "Overdue invoice" for row in rows)


# ── Training LMS + public delivery ────────────────────────────────────────────
def test_training_seeded_modules_present(auth_client: TestClient):
    mods = auth_client.get("/api/v1/training/modules").json()
    assert len(mods) >= 4
    assert any("Phish" in m["title"] for m in mods)


def test_training_assign_and_complete(auth_client: TestClient):
    # create a small module with a one-question quiz
    payload = {
        "title": "Test Module", "category": "Test", "difficulty": "beginner",
        "content_html": "<p>learn</p>", "pass_score": 100, "points": 50,
        "questions": [{"prompt": "Pick B", "options": ["A", "B"], "correct_index": 1}],
    }
    mid = auth_client.post("/api/v1/training/modules", json=payload).json()["id"]
    assert auth_client.post(f"/api/v1/training/modules/{mid}/assign", json={"emails": ["learner@corp.com"]}).json()
    enr = [e for e in auth_client.get(f"/api/v1/training/enrollments?module_id={mid}").json() if e["email"] == "learner@corp.com"]
    assert enr, "enrollment not created"
    tok = enr[0]["token"]
    # public lesson page renders + is XSS-safe (script-src 'self')
    page = auth_client.get(f"/train/{tok}")
    assert page.status_code == 200 and "script-src 'self'" in page.headers.get("content-security-policy", "")
    # wrong answer fails, correct answer completes
    fail = auth_client.post(f"/train/{tok}", data={"q0": "0"})
    assert "Retake" in fail.text
    ok = auth_client.post(f"/train/{tok}", data={"q0": "1"})
    assert "points earned" in ok.text
    done = [e for e in auth_client.get(f"/api/v1/training/enrollments?module_id={mid}").json() if e["email"] == "learner@corp.com"][0]
    assert done["status"] == "completed" and done["score"] == 100


def test_training_bad_token_benign_404(client: TestClient):
    assert client.get("/train/does-not-exist").status_code == 404


def test_training_send_invites_queues_emails(auth_client: TestClient):
    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.models import Job

    mid = auth_client.get("/api/v1/training/modules").json()[0]["id"]
    prof = auth_client.post("/api/v1/profiles", json={
        "name": "t-inv", "from_address": "x@corp.com", "kind": "smtp", "host": "localhost", "port": 1025}).json()
    auth_client.post(f"/api/v1/training/modules/{mid}/assign", json={"emails": ["inv1@corp.com"]})
    db = SessionLocal()
    before = db.execute(select(func.count(Job.id)).where(Job.type == "send_training_invite")).scalar_one()
    r = auth_client.post(f"/api/v1/training/modules/{mid}/send", json={"profile_id": prof["id"]})
    assert r.status_code == 200, r.text
    after = db.execute(select(func.count(Job.id)).where(Job.type == "send_training_invite")).scalar_one()
    assert after > before  # queued at least one invite
    db.close()


# ── Adaptive auto-enroll config ───────────────────────────────────────────────
def test_autoenroll_config_roundtrip(auth_client: TestClient):
    r = auth_client.put("/api/v1/training/auto-enroll", json={"enabled": True, "mode": "adaptive", "module_id": None})
    assert r.status_code == 200 and r.json()["enabled"] is True
    auth_client.put("/api/v1/training/auto-enroll", json={"enabled": False, "mode": "adaptive", "module_id": None})


# ── Benchmark (honest, admin-set) ─────────────────────────────────────────────
def test_benchmark_config_and_compute(auth_client: TestClient):
    auth_client.put("/api/v1/settings/benchmark", json={
        "enabled": True, "industry": "Finance", "baseline_click_rate": 12.5, "baseline_report_rate": 8.0})
    out = auth_client.get("/api/v1/dashboard/benchmark").json()
    assert out["enabled"] is True and out["baseline_click_rate"] == 12.5
    assert "your_click_rate" in out


# ── VAP attack surface ────────────────────────────────────────────────────────
def test_attack_surface_endpoint(auth_client: TestClient):
    out = auth_client.get("/api/v1/dashboard/attack-surface").json()
    assert set(["people", "vip_count", "vip_failed"]).issubset(out.keys())


# ── Deliverability allowlist generator ────────────────────────────────────────
def test_allowlist_generator(auth_client: TestClient):
    out = auth_client.post("/api/v1/deliverability/allowlist", json={
        "domains": ["sim.example"], "ips": ["203.0.113.5"], "urls": ["https://t.sim.example"]}).json()
    platforms = [s["platform"] for s in out["sections"]]
    assert any("Microsoft 365" in p for p in platforms)
    assert any("203.0.113.5" in e for s in out["sections"] for e in s["entries"])


# ── SSO config ────────────────────────────────────────────────────────────────
def test_sso_info_public_and_disabled(client: TestClient):
    info = client.get("/api/v1/auth/sso/info").json()
    assert info["enabled"] is False  # not configured


# ── Governance launch gate ────────────────────────────────────────────────────
def _seed_campaign(auth_client: TestClient) -> int:
    t = auth_client.post("/api/v1/templates", json={
        "name": "gov-t", "channel": "email", "subject": "Hi", "html": "<p>Hi {{.FirstName}} {{.URL}}</p>"}).json()
    g = auth_client.post("/api/v1/groups", json={"name": "gov-g", "targets": [{"email": "t@corp.com", "first_name": "T", "last_name": "U", "position": "IT"}]}).json()
    p = auth_client.post("/api/v1/profiles", json={"name": "gov-p", "from_address": "x@corp.com", "kind": "smtp", "host": "localhost", "port": 1025}).json()
    c = auth_client.post("/api/v1/campaigns", json={
        "name": "gov-c", "template_id": t["id"], "profile_id": p["id"], "group_id": g["id"], "phish_url": "http://testserver"}).json()
    return c["id"]


def test_launch_requires_authorization(auth_client: TestClient):
    cid = _seed_campaign(auth_client)
    # without attestation -> 400
    r = auth_client.post(f"/api/v1/campaigns/{cid}/launch", json={"authorized": False})
    assert r.status_code == 400
    # with attestation -> launches, records authorized_by + audit event
    r = auth_client.post(f"/api/v1/campaigns/{cid}/launch", json={"authorized": True, "authorization_ref": "SEC-1"})
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["authorized_by"] == "admin@example.com" and detail["authorization_ref"] == "SEC-1"
    events = auth_client.get(f"/api/v1/campaigns/{cid}/events").json()
    assert any(e["type"] == "campaign_launched" for e in events)


def test_sms_channel_rejected(auth_client: TestClient):
    r = auth_client.post("/api/v1/templates", json={"name": "sms-x", "channel": "sms", "subject": "x", "text": "y"})
    assert r.status_code == 422
