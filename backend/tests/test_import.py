"""Target import: the /groups/parse-xlsx endpoint parses an uploaded .xlsx into
target rows (headered and headerless), matching the CSV importer's behaviour."""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook


def _xlsx(rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_xlsx_with_header(auth_client):
    data = _xlsx([
        ["First Name", "Last Name", "Email", "Position", "VIP"],
        ["Alice", "Ng", "ALICE@corp.com", "Finance", "yes"],
        ["Bob", "Lee", "bob@corp.com", "Sales", ""],
        ["", "", "", "", ""],  # blank row ignored
    ])
    resp = auth_client.post(
        "/api/v1/groups/parse-xlsx",
        files={"file": ("targets.xlsx", data,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    targets = resp.json()
    assert {t["email"] for t in targets} == {"alice@corp.com", "bob@corp.com"}
    alice = next(t for t in targets if t["email"] == "alice@corp.com")
    assert alice["first_name"] == "Alice" and alice["position"] == "Finance"
    assert alice["is_vip"] is True


def test_parse_xlsx_headerless_and_dedupe(auth_client):
    data = _xlsx([
        ["carol@corp.com", "Carol"],
        ["dan@corp.com"],
        ["CAROL@corp.com", "dup"],  # duplicate (case-insensitive) — dropped
    ])
    resp = auth_client.post(
        "/api/v1/groups/parse-xlsx",
        files={"file": ("t.xlsx", data, "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    emails = [t["email"] for t in resp.json()]
    assert emails == ["carol@corp.com", "dan@corp.com"]


def test_parse_xlsx_rejects_non_xlsx(auth_client):
    resp = auth_client.post(
        "/api/v1/groups/parse-xlsx",
        files={"file": ("not.xlsx", b"this is not a spreadsheet", "application/octet-stream")},
    )
    assert resp.status_code == 400
