"""Shared secret for the Report-Phish add-in ingest endpoint.

Stored as a Setting (plaintext — it's a low-sensitivity internal-tool token that
must be embedded in the add-in the org deploys, and it only gates report
ingestion, never account access). Generated on first use; regenerable by an admin.
"""
from __future__ import annotations

import secrets

from sqlalchemy.orm import Session as DbSession

from ..models import Setting
from ..models.base import utcnow

_KEY = "report_ingest_token"


def _new() -> str:
    return "vpr_" + secrets.token_urlsafe(24)


def get_or_create_report_token(db: DbSession) -> str:
    row = db.get(Setting, _KEY)
    if row is None or not row.value:
        token = _new()
        if row is None:
            db.add(Setting(key=_KEY, value=token, modified_at=utcnow()))
        else:
            row.value = token
            row.modified_at = utcnow()
        db.commit()
        return token
    return row.value


def regenerate_report_token(db: DbSession) -> str:
    row = db.get(Setting, _KEY)
    token = _new()
    if row is None:
        db.add(Setting(key=_KEY, value=token, modified_at=utcnow()))
    else:
        row.value = token
        row.modified_at = utcnow()
    db.commit()
    return token
