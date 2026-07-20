from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ApiKeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyOut):
    # The full key, shown exactly once at creation.
    key: str
