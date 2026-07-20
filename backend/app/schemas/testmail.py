from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class TestEmailRequest(BaseModel):
    profile_id: int
    template_id: int
    to_email: EmailStr
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    position: str | None = Field(default=None, max_length=120)
