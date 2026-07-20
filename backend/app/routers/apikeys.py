"""REST API key management. Each user manages their OWN keys (object-level
authorization, A01). The plaintext key is returned exactly once on creation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user
from ..models import ApiKey, User
from ..schemas.apikey import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from ..schemas.common import Message
from ..security import hash_token, new_api_key

router = APIRouter(
    prefix="/api/v1/apikeys",
    tags=["apikeys"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect)],
)


@router.get("", response_model=list[ApiKeyOut])
def list_keys(db: DbSession = Depends(get_db), user: User = Depends(get_current_user)) -> list[ApiKey]:
    return list(
        db.execute(
            select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
        ).scalars()
    )


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(
    payload: ApiKeyCreate, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> ApiKeyCreated:
    token = new_api_key()
    key = ApiKey(
        user_id=user.id,
        name=payload.name,
        key_hash=hash_token(token),
        prefix=token[:10],
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    # Return the plaintext ONCE; only the hash is stored.
    return ApiKeyCreated(
        id=key.id, name=key.name, prefix=key.prefix, is_active=key.is_active,
        last_used_at=key.last_used_at, created_at=key.created_at, key=token,
    )


@router.delete("/{key_id}", response_model=Message)
def revoke_key(
    key_id: int, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> Message:
    key = db.get(ApiKey, key_id)
    # Object-level auth: you can only revoke your own keys.
    if key is None or key.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    db.delete(key)
    db.commit()
    return Message(detail="API key revoked")
