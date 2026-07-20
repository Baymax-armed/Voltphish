"""Authentication: login / logout / whoami.

- argon2id password verification (A02)
- server-side sessions in HttpOnly; Secure; SameSite=Lax cookies (A07)
- rotate session on login; invalidate server-side on logout
- rate-limited with lockout; generic errors (no user enumeration, A07/A09)
"""
from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..database import get_db
from ..dependencies import SESSION_COOKIE, client_ip, get_current_user
from ..models import Session as SessionModel
from ..models import User, utcnow
from ..csrf import csrf_protect
from ..schemas.auth import AuthOut, LoginRequest, UserOut
from ..schemas.common import Message
from ..schemas.user import ChangePassword
from ..security import (
    hash_password,
    hash_token,
    needs_rehash,
    new_session_token,
    verify_password,
)
from ..services.ratelimit import RateLimiter

log = logging.getLogger("phishsim.auth")
settings = get_settings()
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_login_limiter = RateLimiter(
    max_attempts=settings.login_max_attempts,
    window_seconds=settings.login_window_seconds,
)

_GENERIC_LOGIN_ERROR = "Invalid email or password"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=AuthOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
) -> AuthOut:
    ip = client_ip(request) or "unknown"
    rl_key = f"{payload.email.lower()}|{ip}"

    allowed, retry_after = _login_limiter.check(rl_key)
    if not allowed:
        log.warning("login rate-limited email=%s ip=%s", payload.email, ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.execute(
        select(User).where(User.email == payload.email.lower())
    ).scalar_one_or_none()

    # Always run a hash comparison to avoid timing-based user enumeration.
    stored = user.password_hash if user else "$argon2id$v=19$m=65536,t=3,p=2$" + "A" * 22
    ok = verify_password(stored, payload.password)

    if not user or not user.is_active or not ok:
        _login_limiter.record_failure(rl_key)
        log.info("login failed email=%s ip=%s", payload.email, ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERROR)

    # Opportunistic rehash if parameters changed.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    # Rotate: drop any existing sessions for this user on login (A07).
    db.query(SessionModel).filter(SessionModel.user_id == user.id).delete()

    token = new_session_token()
    csrf = new_session_token()
    db.add(
        SessionModel(
            user_id=user.id,
            token_hash=hash_token(token),
            csrf_token=csrf,
            expires_at=utcnow() + timedelta(seconds=settings.session_ttl_seconds),
            user_agent=(request.headers.get("user-agent") or "")[:255] or None,
            ip=ip[:45],
        )
    )
    db.commit()

    _login_limiter.reset(rl_key)
    _set_session_cookie(response, token)
    log.info("login ok user_id=%s ip=%s", user.id, ip)
    return AuthOut(
        id=user.id, email=user.email, role=user.role, csrf_token=csrf,
        must_change_password=user.must_change_password,
    )


@router.post("/logout", response_model=Message)
def logout(
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
) -> Message:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.query(SessionModel).filter(SessionModel.token_hash == hash_token(token)).delete()
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Message(detail="Logged out")


@router.post("/change-password", response_model=Message, dependencies=[Depends(csrf_protect)])
def change_password(
    payload: ChangePassword,
    request: Request,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False  # requirement satisfied
    # Invalidate all OTHER sessions; keep the current one alive.
    current = request.cookies.get(SESSION_COOKIE)
    current_hash = hash_token(current) if current else ""
    db.query(SessionModel).filter(
        SessionModel.user_id == user.id, SessionModel.token_hash != current_hash
    ).delete()
    db.commit()
    log.info("user %s changed password", user.email)
    return Message(detail="Password changed")


@router.get("/me", response_model=AuthOut)
def me(
    request: Request,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AuthOut:
    token = request.cookies.get(SESSION_COOKIE)
    session = (
        db.query(SessionModel).filter(SessionModel.token_hash == hash_token(token)).one_or_none()
        if token
        else None
    )
    return AuthOut(
        id=user.id,
        email=user.email,
        role=user.role,
        csrf_token=(session.csrf_token if session and session.csrf_token else ""),
        must_change_password=user.must_change_password,
    )
