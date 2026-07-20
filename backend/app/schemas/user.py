from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from ..models import UserRole

MIN_PASSWORD_LEN = 12


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LEN, max_length=1024)
    role: UserRole = UserRole.operator


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=MIN_PASSWORD_LEN, max_length=1024)


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=MIN_PASSWORD_LEN, max_length=1024)


class UserAdminOut(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}
