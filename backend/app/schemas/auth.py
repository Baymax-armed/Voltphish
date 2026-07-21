from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from ..models import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)
    # Optional TOTP code, supplied on the second step when 2FA is enabled.
    code: str | None = Field(default=None, max_length=12)


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
    # True on the login response when a valid password was given but a TOTP code
    # is still required — the SPA then prompts for the code and re-submits.
    two_factor_required: bool = False
    # Whether this account currently has TOTP 2FA enabled (for the Settings UI).
    two_factor_enabled: bool = False
    # Effective granular permissions (admins hold all) — the SPA gates nav on these.
    permissions: list[str] = []
