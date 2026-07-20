from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class TargetIn(BaseModel):
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    position: str | None = Field(default=None, max_length=120)


class TargetOut(TargetIn):
    id: int
    model_config = {"from_attributes": True}


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    targets: list[TargetIn] = Field(default_factory=list, max_length=100_000)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("targets")
    @classmethod
    def _dedupe(cls, targets: list[TargetIn]) -> list[TargetIn]:
        seen: set[str] = set()
        out: list[TargetIn] = []
        for t in targets:
            key = t.email.lower()
            if key not in seen:
                seen.add(key)
                out.append(t)
        return out


class GroupUpdate(GroupCreate):
    pass


class GroupOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    modified_at: datetime
    targets: list[TargetOut]
    model_config = {"from_attributes": True}


class GroupSummary(BaseModel):
    id: int
    name: str
    target_count: int
    modified_at: datetime
