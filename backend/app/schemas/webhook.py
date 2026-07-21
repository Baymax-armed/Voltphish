from __future__ import annotations

from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field


_FORMAT = "^(generic|slack|teams)$"


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: AnyHttpUrl
    secret: str | None = Field(default=None, max_length=1024)
    format: str = Field(default="generic", pattern=_FORMAT)
    is_active: bool = True


class WebhookUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: AnyHttpUrl
    # None => keep existing secret; "" => clear; value => replace.
    secret: str | None = Field(default=None, max_length=1024)
    format: str = Field(default="generic", pattern=_FORMAT)
    is_active: bool = True


class WebhookOut(BaseModel):
    id: int
    name: str
    url: str
    is_active: bool
    has_secret: bool
    format: str
    last_status: int | None = None
    last_error: str | None = None
    last_attempt_at: datetime | None = None
    created_at: datetime
    modified_at: datetime
