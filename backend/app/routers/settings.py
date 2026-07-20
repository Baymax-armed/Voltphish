"""Read-only runtime settings the admin UI needs (e.g. to warn about dev mode)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..config import get_settings
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/v1/settings", tags=["settings"], dependencies=[Depends(get_current_user)])
settings = get_settings()


class RuntimeSettings(BaseModel):
    mail_backend: str
    capture_passwords: bool
    env: str


@router.get("", response_model=RuntimeSettings)
def get_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(
        mail_backend=settings.mail_backend.value,
        capture_passwords=settings.capture_passwords,
        env=settings.env.value,
    )
