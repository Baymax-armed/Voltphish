"""CSRF protection for the cookie-authenticated admin API (double-submit token).

The session carries a random CSRF token. It's handed to the SPA in the login
response and via /auth/me, kept in memory by the client, and sent back as the
`X-CSRF-Token` header on every state-changing request. A cross-site attacker
cannot read that token (it's only ever in a JSON body, unreadable cross-origin),
so it cannot forge the header — while SameSite=Lax already blocks the cookie on
cross-site form posts. Safe methods are exempt.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .database import get_db
from .dependencies import SESSION_COOKIE
from .models import Session as SessionModel
from .security import constant_time_equals, hash_token

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
CSRF_HEADER = "X-CSRF-Token"


def csrf_protect(request: Request, db: DbSession = Depends(get_db)) -> None:
    if request.method in _SAFE_METHODS:
        return

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        # No session cookie => not cookie-auth (e.g. Bearer API key). CSRF only
        # applies to credentials the browser sends automatically, so skip; the
        # auth dependency still enforces a valid key.
        return

    header = request.headers.get(CSRF_HEADER, "")
    if not header:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing CSRF token")

    session = db.execute(
        select(SessionModel).where(SessionModel.token_hash == hash_token(token))
    ).scalar_one_or_none()

    if session is None or not session.csrf_token or not constant_time_equals(
        session.csrf_token, header
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid CSRF token")
