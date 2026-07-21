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
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..database import get_db
from ..dependencies import SESSION_COOKIE, client_ip, get_current_user
from ..models import Session as SessionModel
from ..models import User, UserRole, utcnow
from ..csrf import csrf_protect
from ..permissions import permissions_for
from ..schemas.auth import AuthOut, LoginRequest, UserOut
from ..schemas.common import Message
from ..schemas.user import ChangePassword
from ..security import (
    decrypt_secret,
    encrypt_secret,
    hash_password,
    hash_token,
    needs_rehash,
    new_session_token,
    verify_password,
)
from ..services.ratelimit import make_rate_limiter
from ..services import totp as totp_svc
from ..services.totp import matched_step as totp_matched_step
from ..services.totp import verify as totp_verify
from pydantic import BaseModel, Field as PField

log = logging.getLogger("voltphish.auth")
settings = get_settings()
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_login_limiter = make_rate_limiter(
    max_attempts=settings.login_max_attempts,
    window_seconds=settings.login_window_seconds,
)

_GENERIC_LOGIN_ERROR = "Invalid email or password"

# A valid argon2id hash of a random string, computed once at startup. Verifying a
# submitted password against this performs real argon2 work (and always fails),
# equalizing login latency for non-existent accounts (anti-enumeration).
_DUMMY_HASH = hash_password(new_session_token())


def _mint_session(db: DbSession, user: User, request: Request, response: Response) -> str:
    """Rotate sessions and mint a fresh one + cookie. Returns the CSRF token.
    Shared by password login and SSO callback."""
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
            ip=(client_ip(request) or "unknown")[:45],
        )
    )
    db.commit()
    _set_session_cookie(response, token)
    return csrf


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

    # Always run a REAL argon2 verification even when the user doesn't exist, so
    # login latency doesn't reveal whether an account exists (user enumeration).
    # The dummy must be a valid encoded hash or verify() would bail out early.
    stored = user.password_hash if user else _DUMMY_HASH
    ok = verify_password(stored, payload.password)

    if not user or not user.is_active or not ok:
        _login_limiter.record_failure(rl_key)
        log.info("login failed email=%s ip=%s", payload.email, ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERROR)

    # Second factor (TOTP), if the account has 2FA enabled. The password was
    # correct at this point; require a valid code before minting a session.
    if user.totp_enabled:
        if not payload.code:
            # First step succeeded — ask the SPA for the code. No session, no
            # cookie, and we don't clear the rate-limit counter yet.
            return AuthOut(
                id=0, email=payload.email, role=UserRole.operator, csrf_token="",
                two_factor_required=True,
            )
        secret = decrypt_secret(user.totp_secret_enc)
        step = totp_matched_step(secret, payload.code) if secret else None
        # Reject an invalid code, OR a code whose time-step was already used
        # (anti-replay: a captured code can't be reused within its window).
        if step is None or (user.totp_last_step is not None and step <= user.totp_last_step):
            _login_limiter.record_failure(rl_key)
            log.info("login 2fa failed email=%s ip=%s", payload.email, ip)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication code")
        user.totp_last_step = step

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
        two_factor_enabled=user.totp_enabled,
        permissions=permissions_for(user),
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
        two_factor_enabled=user.totp_enabled,
        permissions=permissions_for(user),
    )


# ---- Two-factor auth (TOTP) enrollment ---------------------------------------


class TotpStatus(BaseModel):
    enabled: bool


class TotpSetupOut(BaseModel):
    secret: str          # base32, shown for manual entry
    otpauth_uri: str
    qr_data_uri: str     # inline PNG for the authenticator to scan


class TotpCode(BaseModel):
    code: str = PField(min_length=6, max_length=12)


@router.get("/2fa/status", response_model=TotpStatus)
def totp_status(user: User = Depends(get_current_user)) -> TotpStatus:
    return TotpStatus(enabled=user.totp_enabled)


@router.post("/2fa/setup", response_model=TotpSetupOut, dependencies=[Depends(csrf_protect)])
def totp_setup(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TotpSetupOut:
    """Generate (or regenerate) a pending TOTP secret. Enrollment isn't active
    until /2fa/enable confirms a code. Refused while 2FA is already enabled —
    the user must disable first (avoids silently rotating a working secret)."""
    if user.totp_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Two-factor is already enabled")
    secret = totp_svc.new_secret()
    user.totp_secret_enc = encrypt_secret(secret)
    db.commit()
    uri = totp_svc.provisioning_uri(secret, user.email)
    log.info("2fa setup started user=%s", user.email)
    return TotpSetupOut(secret=secret, otpauth_uri=uri, qr_data_uri=totp_svc.qr_data_uri(uri))


@router.post("/2fa/enable", response_model=TotpStatus, dependencies=[Depends(csrf_protect)])
def totp_enable(
    payload: TotpCode,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TotpStatus:
    if user.totp_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Two-factor is already enabled")
    secret = decrypt_secret(user.totp_secret_enc) if user.totp_secret_enc else None
    if not secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Start setup first")
    if not totp_verify(secret, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid authentication code")
    user.totp_enabled = True
    db.commit()
    log.info("2fa enabled user=%s", user.email)
    return TotpStatus(enabled=True)


# ---- SSO (OpenID Connect) ----------------------------------------------------


class SsoInfo(BaseModel):
    enabled: bool
    button_label: str


@router.get("/sso/info", response_model=SsoInfo)
def sso_info(db: DbSession = Depends(get_db)) -> SsoInfo:
    """Public: lets the login page decide whether to show the SSO button."""
    from ..services.oidc import get_oidc_config

    cfg = get_oidc_config(db)
    return SsoInfo(enabled=bool(cfg["enabled"] and cfg["issuer"] and cfg["client_id"]),
                   button_label=cfg["button_label"])


def _oidc_redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/api/v1/auth/oidc/callback"


@router.get("/oidc/login")
def oidc_login(request: Request, db: DbSession = Depends(get_db)) -> Response:
    from ..services.oidc import OidcError, begin_login

    try:
        url = begin_login(db, _oidc_redirect_uri(request))
    except OidcError as exc:
        log.warning("oidc login start failed: %s", exc)
        return RedirectResponse(url="/login?sso_error=config", status_code=302)
    return RedirectResponse(url=url, status_code=302)


@router.get("/oidc/callback")
def oidc_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: DbSession = Depends(get_db),
) -> Response:
    from ..services.oidc import OidcError, complete_login

    if error or not code or not state:
        return RedirectResponse(url="/login?sso_error=denied", status_code=302)
    try:
        info = complete_login(db, code=code, state=state, redirect_uri=_oidc_redirect_uri(request))
    except OidcError as exc:
        log.info("oidc callback failed: %s", exc)
        return RedirectResponse(url="/login?sso_error=verify", status_code=302)

    email = info["email"]
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        if not info["auto_provision"]:
            log.info("oidc: no account for %s and auto-provision off", email)
            return RedirectResponse(url="/login?sso_error=noaccount", status_code=302)
        # Auto-provisioning must fail closed: require a verified email AND a
        # configured domain allowlist, so an unverified or arbitrary-domain
        # identity from the IdP can't silently create an account.
        if not info.get("email_verified"):
            log.info("oidc: refusing to provision unverified email %s", email)
            return RedirectResponse(url="/login?sso_error=verify", status_code=302)
        if not info.get("has_allowlist"):
            log.warning("oidc: refusing auto-provision for %s — no domain allowlist configured", email)
            return RedirectResponse(url="/login?sso_error=noaccount", status_code=302)
        user = User(
            email=email,
            # Unusable random password — SSO users authenticate via the IdP only.
            password_hash=hash_password(new_session_token()),
            role=UserRole.operator,
            is_active=True,
            must_change_password=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        log.info("oidc: provisioned new user %s", email)
    if not user.is_active:
        return RedirectResponse(url="/login?sso_error=disabled", status_code=302)

    resp = RedirectResponse(url="/", status_code=302)
    _mint_session(db, user, request, resp)
    log.info("oidc login ok user_id=%s", user.id)
    return resp


@router.post("/2fa/disable", response_model=TotpStatus, dependencies=[Depends(csrf_protect)])
def totp_disable(
    payload: TotpCode,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TotpStatus:
    """Disable 2FA. Requires a current code so a hijacked live session can't
    silently strip the second factor off the account."""
    if not user.totp_enabled:
        return TotpStatus(enabled=False)
    secret = decrypt_secret(user.totp_secret_enc) if user.totp_secret_enc else None
    if not secret or not totp_verify(secret, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid authentication code")
    user.totp_enabled = False
    user.totp_secret_enc = None
    db.commit()
    log.info("2fa disabled user=%s", user.email)
    return TotpStatus(enabled=False)
