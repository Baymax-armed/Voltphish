from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SmsProvider = Literal["console", "textbelt", "twilio", "generic"]


class SmsProfileBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: SmsProvider = "console"
    from_number: str | None = Field(default=None, max_length=40)
    account: str | None = Field(default=None, max_length=255)  # sid / api key / username
    config: str | None = Field(default=None, max_length=4000)  # JSON for generic

    @model_validator(mode="after")
    def _check(self) -> "SmsProfileBase":
        if self.provider == "generic":
            try:
                cfg = json.loads(self.config or "{}")
            except ValueError:
                raise ValueError("config must be valid JSON for the generic provider")
            if not cfg.get("url"):
                raise ValueError("generic provider config needs a 'url'")
        return self


class SmsProfileCreate(SmsProfileBase):
    secret: str | None = Field(default=None, max_length=1024)  # auth token / key / secret


class SmsProfileUpdate(SmsProfileBase):
    secret: str | None = Field(default=None, max_length=1024)


class SmsProfileOut(SmsProfileBase):
    id: int
    has_secret: bool
    created_at: datetime
    modified_at: datetime


class SmsTestRequest(BaseModel):
    to: str = Field(min_length=1, max_length=40)
    message: str = Field(min_length=1, max_length=1000)
