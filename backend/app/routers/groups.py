"""Recipient group CRUD. All routes require authentication (A01)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..csrf import csrf_protect
from ..dependencies import get_current_user
from ..models import Group, Target
from ..schemas.common import Message
from ..schemas.group import GroupCreate, GroupOut, GroupSummary, GroupUpdate

router = APIRouter(
    prefix="/api/v1/groups",
    tags=["groups"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect)],
)


@router.get("", response_model=list[GroupSummary])
def list_groups(db: DbSession = Depends(get_db)) -> list[GroupSummary]:
    groups = db.execute(select(Group).order_by(Group.name)).scalars()
    return [
        GroupSummary(
            id=g.id, name=g.name, target_count=len(g.targets), modified_at=g.modified_at
        )
        for g in groups
    ]


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(payload: GroupCreate, db: DbSession = Depends(get_db)) -> Group:
    group = Group(name=payload.name)
    group.targets = [
        Target(
            email=str(t.email).lower(),
            phone=t.phone,
            first_name=t.first_name,
            last_name=t.last_name,
            position=t.position,
        )
        for t in payload.targets
    ]
    db.add(group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A group with that name already exists")
    db.refresh(group)
    return group


@router.get("/{group_id}", response_model=GroupOut)
def get_group(group_id: int, db: DbSession = Depends(get_db)) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return group


@router.put("/{group_id}", response_model=GroupOut)
def update_group(group_id: int, payload: GroupUpdate, db: DbSession = Depends(get_db)) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    group.name = payload.name
    # Replace membership wholesale (cascade delete-orphan cleans old rows).
    group.targets = [
        Target(
            email=str(t.email).lower(),
            phone=t.phone,
            first_name=t.first_name,
            last_name=t.last_name,
            position=t.position,
        )
        for t in payload.targets
    ]
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A group with that name already exists")
    db.refresh(group)
    return group


@router.delete("/{group_id}", response_model=Message)
def delete_group(group_id: int, db: DbSession = Depends(get_db)) -> Message:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    db.delete(group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This group is still used by a campaign — delete those campaigns first.")
    return Message(detail="Group deleted")
