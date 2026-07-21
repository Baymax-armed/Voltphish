"""Ingest an email reported through the Report-Phish add-in.

Shared by the add-in HTTP endpoint. If the reported message carries a VoltPhish
tracking token, it's one of our simulations → record a `reported` event (credit
the Security Champion). Otherwise it's a real suspicious email → store it for the
security team to triage. Matching mirrors the IMAP poller so both report paths
behave identically.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..models import EventType, ReportedEmail, ReportStatus, Result
from .events import record_event

log = logging.getLogger("phishsim.report")

# Same tracking tokens the IMAP poller matches: /c/{rid} /t/{rid}.png /a/{rid}.png
# /q/{rid}.png /p/{rid} /r/{rid} /report?rid= /learn/{rid}, plus short links /s/.
_RID_RE = re.compile(r"/(?:c|t|a|q|p|r|learn)/([A-Za-z0-9_\-]{6,})", re.IGNORECASE)
_RID_QS_RE = re.compile(r"[?&]rid=([A-Za-z0-9_\-]{6,})", re.IGNORECASE)
_SHORT_RE = re.compile(r"/s/([A-Za-z0-9]{4,})", re.IGNORECASE)

_PREVIEW_LEN = 4000


def _match_result(db: DbSession, *, body: str, reporter: str | None) -> Result | None:
    haystack = body or ""
    for rid in set(_RID_RE.findall(haystack)) | set(_RID_QS_RE.findall(haystack)):
        r = db.query(Result).filter(Result.rid == rid).one_or_none()
        if r is not None:
            return r
    for code in set(_SHORT_RE.findall(haystack)):
        r = db.query(Result).filter(Result.short_code == code).one_or_none()
        if r is not None:
            return r
    if reporter and "@" in reporter:
        r = (
            db.execute(
                select(Result).where(func.lower(Result.email) == reporter.lower()).order_by(Result.id.desc())
            )
            .scalars()
            .first()
        )
        if r is not None:
            return r
    return None


def ingest_report(
    db: DbSession,
    *,
    reporter_email: str | None,
    subject: str | None,
    sender: str | None,
    body: str,
    headers: str | None = None,
    source: str = "addin",
) -> dict:
    """Record a reported email. Returns {"simulation": bool, "detail": str}.

    Commits its own work. The caller (HTTP endpoint) has already authenticated."""
    result = _match_result(db, body=body, reporter=reporter_email)
    is_sim = result is not None

    row = ReportedEmail(
        reporter_email=(reporter_email or None),
        subject=(subject or None) and subject[:998],
        sender=(sender or None) and sender[:320],
        body_preview=(body or "")[:_PREVIEW_LEN] or None,
        headers=(headers or "")[:_PREVIEW_LEN] or None,
        source=source,
        is_simulation=is_sim,
        matched_rid=result.rid if result else None,
        matched_result_id=result.id if result else None,
        status=ReportStatus.benign if is_sim else ReportStatus.new,
    )
    db.add(row)

    if result is not None:
        # Credit the champion (idempotent-ish: reported status is terminal-safe).
        record_event(db, campaign_id=result.campaign_id, rid=result.rid, type=EventType.reported)
        db.commit()
        log.info("report: simulation reported rid=%s reporter=%s", result.rid, reporter_email)
        return {
            "simulation": True,
            "detail": "Thanks — you correctly reported a simulated phishing test. Nice catch!",
        }

    db.commit()
    log.info("report: real suspicious email queued reporter=%s subject=%r", reporter_email, (subject or "")[:80])
    return {
        "simulation": False,
        "detail": "Thanks for reporting. Your security team has been notified and will review this message.",
    }
