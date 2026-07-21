"""Reusable FastAPI dependencies: session-cookie auth and role gates.

Fail closed (CLAUDE.md §0.3): any missing/expired/invalid session -> 401.
Authorization is enforced here on the server, never assumed from the UI (A01).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .config import get_settings
from .database import get_db
from .models import ApiKey
from .models import Session as SessionModel
from .models import User, UserRole
from .models import utcnow
from .security import hash_token

SESSION_COOKIE = "voltphish_session"
settings = get_settings()


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer ") :].strip() or None
    return None


def _user_from_api_key(request: Request, db: DbSession) -> User | None:
    token = _bearer_token(request)
    if not token:
        return None
    key = db.execute(
        select(ApiKey).where(ApiKey.key_hash == hash_token(token))
    ).scalar_one_or_none()
    if key is None or not key.is_active:
        return None
    user = db.get(User, key.user_id)
    if user is None or not user.is_active:
        return None
    key.last_used_at = utcnow()
    db.commit()
    return user


def client_ip(request: Request) -> str | None:
    """Best-effort client IP. Only trust proxy headers if you run behind a
    trusted proxy that sets them; otherwise this uses the socket peer."""
    return request.client.host if request.client else None


def get_current_user(
    request: Request,
    db: DbSession = Depends(get_db),
) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        # No session cookie: try REST API key (Authorization: Bearer <key>).
        user = _user_from_api_key(request, db)
        if user is not None:
            return user
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session = db.execute(
        select(SessionModel).where(SessionModel.token_hash == hash_token(token))
    ).scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    if session.expires_at <= datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account disabled")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role is not UserRole.admin:
        # 403: authenticated but not authorized.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
