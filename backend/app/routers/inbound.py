"""Public, token-gated ingest for the Report-Phish add-in.

The Outlook/Gmail add-in POSTs the reported message here. Auth is a shared
report token (an internal-tool secret embedded in the add-in the org deploys),
checked in constant time. Rate-limited per source IP to blunt abuse. No session
cookie — this is called from the user's mail client, not the SPA.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..dependencies import client_ip
from ..services.inbound_report import ingest_report
from ..services.ratelimit import RateLimiter
from ..services.report_token import get_or_create_report_token

log = logging.getLogger("phishsim.inbound")
router = APIRouter(prefix="/api/v1/inbound", tags=["inbound"])

_report_limiter = RateLimiter(max_attempts=30, window_seconds=60)


class ReportIn(BaseModel):
    reporter_email: str | None = Field(default=None, max_length=320)
    subject: str | None = Field(default=None, max_length=998)
    sender: str | None = Field(default=None, max_length=320)
    body: str = Field(default="", max_length=200_000)
    headers: str | None = Field(default=None, max_length=200_000)


class ReportOut(BaseModel):
    simulation: bool
    detail: str


@router.post("/report", response_model=ReportOut)
def report(
    payload: ReportIn,
    request: Request,
    db: DbSession = Depends(get_db),
    x_report_token: str = Header(default=""),
) -> ReportOut:
    ip = client_ip(request) or "unknown"
    allowed, retry_after = _report_limiter.check(ip)
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reports. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )

    expected = get_or_create_report_token(db)
    if not x_report_token or not hmac.compare_digest(x_report_token, expected):
        _report_limiter.record_failure(ip)
        log.warning("inbound report: bad token ip=%s", ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid report token")

    out = ingest_report(
        db,
        reporter_email=payload.reporter_email,
        subject=payload.subject,
        sender=payload.sender,
        body=payload.body,
        headers=payload.headers,
        source="addin",
    )
    return ReportOut(**out)
