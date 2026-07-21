"""User management — admin only (CLAUDE.md A01 object/role authorization).

Guards against foot-guns: you can't delete or de-admin yourself, and you can't
remove the last remaining active admin (fail closed on lockout)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user
from ..permissions import require_permission

require_admin = require_permission("users:manage")
from ..models import Session as SessionModel
from ..models import User, UserRole
from ..permissions import PERMISSIONS, sanitize_permissions
from ..schemas.common import Message
from ..schemas.user import PasswordReset, UserAdminOut, UserCreate, UserUpdate
from ..security import hash_password

log = logging.getLogger("voltphish.users")

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect), Depends(require_admin)],
)


def _active_admin_count(db: DbSession) -> int:
    return db.execute(
        select(func.count(User.id)).where(User.role == UserRole.admin, User.is_active.is_(True))
    ).scalar_one()


class PermissionInfo(BaseModel):
    key: str
    label: str


@router.get("/permissions", response_model=list[PermissionInfo])
def list_permissions() -> list[PermissionInfo]:
    """Catalog of delegatable permissions for the role editor."""
    return [PermissionInfo(key=k, label=v) for k, v in PERMISSIONS.items()]


@router.get("", response_model=list[UserAdminOut])
def list_users(db: DbSession = Depends(get_db)) -> list[UserAdminOut]:
    users = db.execute(select(User).order_by(User.email)).scalars()
    return [UserAdminOut.from_user(u) for u in users]


def _require_admin_for_privilege(me: User, *, setting_admin: bool, granting_perms: bool) -> None:
    """Only a true admin may hand out the admin role or delegated permissions.
    A delegated `users:manage` operator can manage the user lifecycle but must
    NOT be able to escalate privileges (self or others) — that would make the
    delegated grant equivalent to full admin (SECURITY: privilege escalation)."""
    if (setting_admin or granting_perms) and me.role is not UserRole.admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only an admin can assign the admin role or grant permissions.",
        )


@router.post("", response_model=UserAdminOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: DbSession = Depends(get_db),
    me: User = Depends(get_current_user),
) -> UserAdminOut:
    _require_admin_for_privilege(
        me,
        setting_admin=payload.role is UserRole.admin,
        granting_perms=bool(payload.permissions),
    )
    user = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        extra_permissions=sanitize_permissions(payload.permissions),
        # The admin sets an initial password; the user must change it on first login.
        must_change_password=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with that email already exists")
    db.refresh(user)
    log.info("admin created user %s (role=%s)", user.email, user.role.value)
    return UserAdminOut.from_user(user)


@router.put("/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: DbSession = Depends(get_db),
    me: User = Depends(get_current_user),
) -> UserAdminOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    # Privilege-affecting changes (role or delegated permissions) require a true
    # admin — a delegated `users:manage` operator must not be able to escalate.
    _require_admin_for_privilege(
        me,
        setting_admin=(payload.role is not None and payload.role is not user.role),
        granting_perms=payload.permissions is not None,
    )

    would_demote = payload.role is not None and payload.role is not UserRole.admin
    would_disable = payload.is_active is False
    if user.role is UserRole.admin and (would_demote or would_disable):
        # Don't allow removing the last admin, or self-demotion (lockout).
        if user.id == me.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot demote or disable yourself")
        if _active_admin_count(db) <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove the last active admin")

    if payload.role is not None:
        user.role = payload.role
    if payload.permissions is not None:
        user.extra_permissions = sanitize_permissions(payload.permissions)
    if payload.is_active is not None:
        user.is_active = payload.is_active
        if not payload.is_active:
            # Kill their sessions immediately when disabled.
            db.query(SessionModel).filter(SessionModel.user_id == user.id).delete()
    db.commit()
    db.refresh(user)
    return UserAdminOut.from_user(user)


@router.post("/{user_id}/reset-password", response_model=Message)
def reset_password(user_id: int, payload: PasswordReset, db: DbSession = Depends(get_db)) -> Message:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.password_hash = hash_password(payload.password)
    # Admin-set password is temporary — force the user to change it on next login.
    user.must_change_password = True
    # Force re-login everywhere after an admin reset.
    db.query(SessionModel).filter(SessionModel.user_id == user.id).delete()
    db.commit()
    log.info("admin reset password for %s", user.email)
    return Message(detail="Password reset")


@router.delete("/{user_id}", response_model=Message)
def delete_user(
    user_id: int, db: DbSession = Depends(get_db), me: User = Depends(get_current_user)
) -> Message:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == me.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot delete yourself")
    if user.role is UserRole.admin and _active_admin_count(db) <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete the last active admin")
    db.delete(user)
    db.commit()
    log.info("admin deleted user %s", user.email)
    return Message(detail="User deleted")
