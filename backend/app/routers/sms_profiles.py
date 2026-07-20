"""SMS sending profile CRUD + verify + test. Secrets encrypted at rest."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user
from ..models import SmsProfile
from ..schemas.common import Message
from ..schemas.sms_profile import (
    SmsProfileCreate,
    SmsProfileOut,
    SmsProfileUpdate,
    SmsTestRequest,
)
from ..security import encrypt_secret
from ..services.smsapi import SmsError, send_sms, verify_sms

router = APIRouter(
    prefix="/api/v1/sms-profiles",
    tags=["sms"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect)],
)


def _to_out(p: SmsProfile) -> SmsProfileOut:
    return SmsProfileOut(
        id=p.id, name=p.name, provider=p.provider, from_number=p.from_number,
        account=p.account, config=p.config, has_secret=bool(p.secret_encrypted),
        created_at=p.created_at, modified_at=p.modified_at,
    )


@router.get("", response_model=list[SmsProfileOut])
def list_sms(db: DbSession = Depends(get_db)) -> list[SmsProfileOut]:
    return [_to_out(p) for p in db.execute(select(SmsProfile).order_by(SmsProfile.name)).scalars()]


@router.post("", response_model=SmsProfileOut, status_code=201)
def create_sms(payload: SmsProfileCreate, db: DbSession = Depends(get_db)) -> SmsProfileOut:
    p = SmsProfile(
        name=payload.name, provider=payload.provider, from_number=payload.from_number,
        account=payload.account, config=payload.config,
        secret_encrypted=encrypt_secret(payload.secret),
    )
    db.add(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An SMS profile with that name already exists")
    db.refresh(p)
    return _to_out(p)


@router.put("/{profile_id}", response_model=SmsProfileOut)
def update_sms(profile_id: int, payload: SmsProfileUpdate, db: DbSession = Depends(get_db)) -> SmsProfileOut:
    p = db.get(SmsProfile, profile_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SMS profile not found")
    p.name = payload.name
    p.provider = payload.provider
    p.from_number = payload.from_number
    p.account = payload.account
    p.config = payload.config
    if payload.secret is not None:
        p.secret_encrypted = encrypt_secret(payload.secret) if payload.secret else None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An SMS profile with that name already exists")
    db.refresh(p)
    return _to_out(p)


@router.post("/{profile_id}/verify", response_model=Message)
async def verify_profile(profile_id: int, db: DbSession = Depends(get_db)) -> Message:
    p = db.get(SmsProfile, profile_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SMS profile not found")
    try:
        await verify_sms(p)
    except SmsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"SMS check failed: {exc}")
    return Message(detail=f"{p.provider.title()} looks configured. Send a test to be sure.")


@router.post("/{profile_id}/test", response_model=Message)
async def test_sms(profile_id: int, payload: SmsTestRequest, db: DbSession = Depends(get_db)) -> Message:
    p = db.get(SmsProfile, profile_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SMS profile not found")
    try:
        await send_sms(p, payload.to, payload.message)
    except SmsError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"SMS send failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"SMS send failed: {type(exc).__name__}")
    where = "outbox (console)" if p.provider == "console" else p.provider
    return Message(detail=f"Test SMS sent to {payload.to} via {where}.")


@router.delete("/{profile_id}", response_model=Message)
def delete_sms(profile_id: int, db: DbSession = Depends(get_db)) -> Message:
    p = db.get(SmsProfile, profile_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SMS profile not found")
    db.delete(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This SMS profile is still used by a campaign — delete those campaigns first.")
    return Message(detail="SMS profile deleted")
