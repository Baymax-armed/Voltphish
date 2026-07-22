"""Sending profile (SMTP) CRUD. Passwords are encrypted at rest and never
returned. All routes require authentication (A01)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..database import get_db
from ..csrf import csrf_protect
from ..dependencies import get_current_user
from ..models import SendingProfile
from ..schemas.common import Message
from ..schemas.profile import HeaderItem, ProfileCreate, ProfileOut, ProfileUpdate
from ..security import encrypt_secret
from ..services.emailapi import EmailApiError, verify_api
from ..services.mailer import SmtpVerifyError, verify_smtp


def _headers_to_json(headers: list[HeaderItem]) -> str | None:
    if not headers:
        return None
    return json.dumps([{"key": h.key, "value": h.value} for h in headers])


def _headers_from_json(raw: str | None) -> list[HeaderItem]:
    if not raw:
        return []
    try:
        return [HeaderItem(**h) for h in json.loads(raw)]
    except (ValueError, TypeError):
        return []

router = APIRouter(
    prefix="/api/v1/profiles",
    tags=["profiles"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect)],
)


def _to_out(p: SendingProfile) -> ProfileOut:
    return ProfileOut(
        id=p.id,
        name=p.name,
        from_address=p.from_address,
        envelope_sender=p.envelope_sender,
        kind=p.kind,
        host=p.host,
        port=p.port,
        username=p.username,
        headers=_headers_from_json(p.headers),
        use_starttls=p.use_starttls,
        use_ssl=p.use_ssl,
        ignore_cert_errors=p.ignore_cert_errors,
        api_provider=p.api_provider,
        api_domain=p.api_domain,
        has_password=bool(p.password_encrypted),
        has_api_key=bool(p.api_key_encrypted),
        created_at=p.created_at,
        modified_at=p.modified_at,
    )


@router.get("", response_model=list[ProfileOut])
def list_profiles(db: DbSession = Depends(get_db)) -> list[ProfileOut]:
    return [_to_out(p) for p in db.execute(select(SendingProfile).order_by(SendingProfile.name)).scalars()]


@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
async def create_profile(payload: ProfileCreate, db: DbSession = Depends(get_db)) -> ProfileOut:
    p = SendingProfile(
        name=payload.name,
        from_address=str(payload.from_address),
        envelope_sender=str(payload.envelope_sender) if payload.envelope_sender else None,
        kind=payload.kind,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        headers=_headers_to_json(payload.headers),
        password_encrypted=encrypt_secret(payload.password),
        use_starttls=payload.use_starttls,
        use_ssl=payload.use_ssl,
        ignore_cert_errors=payload.ignore_cert_errors,
        api_provider=payload.api_provider,
        api_domain=payload.api_domain,
        api_key_encrypted=encrypt_secret(payload.api_key),
    )
    # A profile can't be saved unless it actually connects/authenticates.
    if get_settings().require_profile_verify:
        await _verify_or_400(p)
    db.add(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A profile with that name already exists")
    db.refresh(p)
    return _to_out(p)


@router.put("/{profile_id}", response_model=ProfileOut)
async def update_profile(
    profile_id: int, payload: ProfileUpdate, db: DbSession = Depends(get_db)
) -> ProfileOut:
    p = db.get(SendingProfile, profile_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    p.name = payload.name
    p.from_address = str(payload.from_address)
    p.envelope_sender = str(payload.envelope_sender) if payload.envelope_sender else None
    p.kind = payload.kind
    p.host = payload.host
    p.port = payload.port
    p.username = payload.username
    p.headers = _headers_to_json(payload.headers)
    p.use_starttls = payload.use_starttls
    p.use_ssl = payload.use_ssl
    p.ignore_cert_errors = payload.ignore_cert_errors
    p.api_provider = payload.api_provider
    p.api_domain = payload.api_domain
    # None => keep existing; "" => clear; value => replace (re-encrypt).
    if payload.password is not None:
        p.password_encrypted = encrypt_secret(payload.password) if payload.password else None
    if payload.api_key is not None:
        p.api_key_encrypted = encrypt_secret(payload.api_key) if payload.api_key else None
    # Re-verify the (updated) profile before persisting the changes.
    if get_settings().require_profile_verify:
        await _verify_or_400(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A profile with that name already exists")
    db.refresh(p)
    return _to_out(p)


async def _verify_or_400(p: SendingProfile) -> None:
    """Force a live connectivity/credential check; raise 400 (blocking the save)
    if it fails, so a broken Sending Profile can never be persisted."""
    if p.kind == "api":
        try:
            await verify_api(p)
        except EmailApiError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Can't save — API check failed: {exc}")
        return
    try:
        await verify_smtp(p)
    except SmtpVerifyError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Can't save — SMTP connection failed: {exc} Hint: {_tls_hint(p)}",
        )


def _tls_hint(p: SendingProfile) -> str:
    """A targeted suggestion for the most common TLS/port misconfigurations."""
    if p.port == 465 and not p.use_ssl:
        return "Port 465 needs 'Use implicit SSL/TLS' ON (and STARTTLS OFF)."
    if p.port in (587, 25) and p.use_ssl:
        return "Port 587/25 usually needs STARTTLS, not implicit SSL — turn 'Use implicit SSL/TLS' OFF."
    if not p.use_ssl and not p.use_starttls:
        return "No encryption is selected — most providers require STARTTLS (587) or SSL (465)."
    return "Check the host/port are correct and that outbound SMTP isn't blocked by a firewall (common on cloud/home networks)."


@router.post("/{profile_id}/verify", response_model=Message)
async def verify_profile(profile_id: int, db: DbSession = Depends(get_db)) -> Message:
    """Check that this profile's credentials actually work (no email is sent).
    SMTP profiles connect + authenticate; API profiles validate the key via the
    provider. Ignores the console dev mode."""
    p = db.get(SendingProfile, profile_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")

    if p.kind == "api":
        try:
            await verify_api(p)
        except EmailApiError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"API check failed: {exc}")
        return Message(detail=f"{(p.api_provider or 'API').title()} API key is valid. Ready to send.")

    try:
        await verify_smtp(p)
    except SmtpVerifyError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"SMTP check failed: {exc} Hint: {_tls_hint(p)}"
        )
    return Message(detail=f"Connected to {p.host}:{p.port} successfully. Credentials look good.")


@router.delete("/{profile_id}", response_model=Message)
def delete_profile(profile_id: int, db: DbSession = Depends(get_db)) -> Message:
    p = db.get(SendingProfile, profile_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    db.delete(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This profile is still used by one or more campaigns — delete those campaigns first.",
        )
    return Message(detail="Profile deleted")
