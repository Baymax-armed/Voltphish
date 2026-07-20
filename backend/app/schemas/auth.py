from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from ..models import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: UserRole

    model_config = {"from_attributes": True}


class AuthOut(BaseModel):
    """User identity plus the per-session CSRF token the SPA must echo back."""

    id: int
    email: EmailStr
    role: UserRole
    csrf_token: str
    must_change_password: bool = False
