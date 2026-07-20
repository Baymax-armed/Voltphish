"""Runtime settings the admin UI reads/writes (dev-mode banner + AI config)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user, require_admin
from ..models import Setting
from ..models.base import utcnow
from ..schemas.common import Message
from ..security import encrypt_secret
from ..services.ai import PROVIDERS, AiError, get_ai_config, ping

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


# ── AI provider config (admin) ────────────────────────────────────────────────
def _set(db: DbSession, key: str, value: str | None) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value, modified_at=utcnow()))
    else:
        row.value = value
        row.modified_at = utcnow()


class ProviderInfo(BaseModel):
    value: str
    label: str


class AiSettingsOut(BaseModel):
    provider: str
    model: str
    has_key: bool
    key_hint: str  # masked last 4 chars; empty if none
    providers: list[ProviderInfo]


class AiSettingsUpdate(BaseModel):
    provider: str = Field(default="anthropic")
    model: str = Field(min_length=1, max_length=100)
    # None => keep existing key for this provider; "" => clear; value => replace.
    api_key: str | None = Field(default=None, max_length=400)


@router.get("/ai", response_model=AiSettingsOut, dependencies=[Depends(require_admin)])
def get_ai_settings(db: DbSession = Depends(get_db)) -> AiSettingsOut:
    cfg = get_ai_config(db)
    key = cfg["api_key"]
    return AiSettingsOut(
        provider=cfg["provider"],
        model=cfg["model"],
        has_key=bool(key),
        key_hint=("…" + key[-4:]) if key else "",
        providers=[ProviderInfo(value=k, label=v["label"]) for k, v in PROVIDERS.items()],
    )


@router.put("/ai", response_model=AiSettingsOut, dependencies=[Depends(require_admin), Depends(csrf_protect)])
def update_ai_settings(payload: AiSettingsUpdate, db: DbSession = Depends(get_db)) -> AiSettingsOut:
    provider = payload.provider if payload.provider in PROVIDERS else "anthropic"
    _set(db, "ai_provider", provider)
    _set(db, "ai_model", payload.model)
    if payload.api_key is not None:
        _set(db, f"ai_key_{provider}_enc", encrypt_secret(payload.api_key) if payload.api_key else None)
    db.commit()
    return get_ai_settings(db)


@router.post("/ai/test", response_model=Message, dependencies=[Depends(require_admin), Depends(csrf_protect)])
async def test_ai_settings(db: DbSession = Depends(get_db)) -> Message:
    """Ping the model with a tiny prompt so the admin can confirm it works."""
    cfg = get_ai_config(db)
    if not cfg["api_key"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No API key set for this provider. Add one and save first.")
    try:
        await ping(provider=cfg["provider"], api_key=cfg["api_key"], model=cfg["model"], base_url=cfg["base_url"])
    except AiError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return Message(detail=f"Connected — {cfg['model']} responded. AI generation is ready.")
