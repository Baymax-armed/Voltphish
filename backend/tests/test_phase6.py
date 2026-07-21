"""Phase 6: open-tracking pixel, report alias, attachments, import-site."""
from __future__ import annotations

import base64

from fastapi.testclient import TestClient


def test_open_pixel_is_png_and_uncached(client: TestClient) -> None:
    r = client.get("/t/whatever.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"  # valid PNG signature
    assert "no-store" in r.headers.get("cache-control", "")


def test_report_query_alias(auth_client: TestClient) -> None:
    # Build a launched campaign, then hit /report?rid=... and confirm "reported".
    tpl = auth_client.post("/api/v1/templates", json={"name": "r tpl", "subject": "s", "text": "x {{.URL}}"}).json()
    prof = auth_client.post("/api/v1/profiles", json={"name": "r prof", "from_address": "it@e.com", "host": "localhost", "port": 1025}).json()
    grp = auth_client.post("/api/v1/groups", json={"name": "r grp", "targets": [{"email": "r@e.com", "first_name": "R"}]}).json()
    camp = auth_client.post("/api/v1/campaigns", json={
        "name": "r camp", "template_id": tpl["id"], "profile_id": prof["id"],
        "group_id": grp["id"], "phish_url": "http://testserver"}).json()
    auth_client.post(f"/api/v1/campaigns/{camp['id']}/launch", json={"authorized": True})

    import time
    rid = None
    for _ in range(50):
        d = auth_client.get(f"/api/v1/campaigns/{camp['id']}").json()
        if d["results"]:
            rid = d["results"][0]["rid"]
            if d["stats"]["sent"] >= 1:
                break
        time.sleep(0.1)
    assert rid
    assert auth_client.get(f"/report?rid={rid}").status_code == 200
    stats = auth_client.get(f"/api/v1/campaigns/{camp['id']}").json()["stats"]
    assert stats["reported"] == 1


def test_attachment_allowlist_and_size(auth_client: TestClient) -> None:
    tpl = auth_client.post("/api/v1/templates", json={"name": "att tpl", "subject": "s", "text": "t"}).json()
    tid = tpl["id"]
    good = base64.b64encode(b"%PDF-1.4 fake invoice").decode()

    ok = auth_client.post(f"/api/v1/templates/{tid}/attachments",
                          json={"filename": "invoice.pdf", "content_type": "application/pdf", "content_b64": good})
    assert ok.status_code == 201, ok.text
    assert ok.json()["filename"] == "invoice.pdf"

    # Executable extension rejected.
    bad = auth_client.post(f"/api/v1/templates/{tid}/attachments",
                           json={"filename": "evil.exe", "content_type": "application/octet-stream", "content_b64": good})
    assert bad.status_code == 400

    # Path traversal in filename is stripped to a basename.
    trav = auth_client.post(f"/api/v1/templates/{tid}/attachments",
                            json={"filename": "../../etc/passwd.txt", "content_type": "text/plain", "content_b64": good})
    assert trav.status_code == 201
    assert trav.json()["filename"] == "passwd.txt"

    # Attachment shows up on the template and can be deleted.
    listed = auth_client.get(f"/api/v1/templates/{tid}").json()["attachments"]
    assert len(listed) == 2
    aid = listed[0]["id"]
    assert auth_client.delete(f"/api/v1/templates/{tid}/attachments/{aid}").status_code == 200


def test_import_site_rejects_internal(auth_client: TestClient) -> None:
    r = auth_client.post("/api/v1/pages/import-site", json={"url": "http://169.254.169.254/latest"})
    assert r.status_code == 400
