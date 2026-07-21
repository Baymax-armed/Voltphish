"""Runtime settings the admin UI reads/writes (dev-mode banner + AI config)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user
from ..permissions import require_permission

require_admin = require_permission("settings:manage")
from ..models import Setting
from ..models.base import utcnow
from ..schemas.common import Message
from ..security import encrypt_secret
from ..services.ai import PROVIDERS, AiError, get_ai_config, ping
from ..services.imap_monitor import ImapError, get_imap_config, test_imap

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


# ── IMAP reported-phish monitoring (admin) ────────────────────────────────────
class ImapSettingsOut(BaseModel):
    enabled: bool
    host: str
    port: int
    username: str
    ssl: bool
    folder: str
    has_password: bool


class ImapSettingsUpdate(BaseModel):
    enabled: bool = False
    host: str = Field(default="", max_length=255)
    port: int = Field(default=993, ge=1, le=65535)
    username: str = Field(default="", max_length=320)
    ssl: bool = True
    folder: str = Field(default="INBOX", max_length=120)
    # None => keep existing password; "" => clear; value => replace.
    password: str | None = Field(default=None, max_length=400)


def _imap_out(db: DbSession) -> ImapSettingsOut:
    cfg = get_imap_config(db)
    return ImapSettingsOut(
        enabled=cfg["enabled"], host=cfg["host"], port=cfg["port"],
        username=cfg["username"], ssl=cfg["ssl"], folder=cfg["folder"],
        has_password=bool(cfg["password"]),
    )


@router.get("/imap", response_model=ImapSettingsOut, dependencies=[Depends(require_admin)])
def get_imap_settings(db: DbSession = Depends(get_db)) -> ImapSettingsOut:
    return _imap_out(db)


@router.put("/imap", response_model=ImapSettingsOut, dependencies=[Depends(require_admin), Depends(csrf_protect)])
def update_imap_settings(payload: ImapSettingsUpdate, db: DbSession = Depends(get_db)) -> ImapSettingsOut:
    _set(db, "imap_enabled", "1" if payload.enabled else "0")
    _set(db, "imap_host", payload.host.strip())
    _set(db, "imap_port", str(payload.port))
    _set(db, "imap_username", payload.username.strip())
    _set(db, "imap_ssl", "1" if payload.ssl else "0")
    _set(db, "imap_folder", payload.folder.strip() or "INBOX")
    if payload.password is not None:
        _set(db, "imap_password_enc", encrypt_secret(payload.password) if payload.password else None)
    db.commit()
    return _imap_out(db)


@router.post("/imap/test", response_model=Message, dependencies=[Depends(require_admin), Depends(csrf_protect)])
async def test_imap_settings(db: DbSession = Depends(get_db)) -> Message:
    """Connect to the mailbox to confirm the credentials work."""
    import asyncio

    cfg = get_imap_config(db)
    try:
        count = await asyncio.to_thread(test_imap, cfg)
    except ImapError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return Message(detail=f"Connected — mailbox '{cfg['folder']}' has {count} message(s). Monitoring is active.")


# ── SSO (OpenID Connect) config (admin) ───────────────────────────────────────
class SsoSettingsOut(BaseModel):
    enabled: bool
    issuer: str
    client_id: str
    allowed_domains: str
    auto_provision: bool
    button_label: str
    has_secret: bool
    redirect_uri: str


class SsoSettingsUpdate(BaseModel):
    enabled: bool = False
    issuer: str = Field(default="", max_length=255)
    client_id: str = Field(default="", max_length=255)
    # None => keep existing secret; "" => clear; value => replace.
    client_secret: str | None = Field(default=None, max_length=400)
    allowed_domains: str = Field(default="", max_length=500)
    auto_provision: bool = False
    button_label: str = Field(default="Sign in with SSO", max_length=60)


def _sso_out(db: DbSession, redirect_uri: str) -> SsoSettingsOut:
    from ..services.oidc import get_oidc_config

    cfg = get_oidc_config(db)
    return SsoSettingsOut(
        enabled=cfg["enabled"], issuer=cfg["issuer"], client_id=cfg["client_id"],
        allowed_domains=",".join(cfg["allowed_domains"]), auto_provision=cfg["auto_provision"],
        button_label=cfg["button_label"], has_secret=bool(cfg["client_secret"]),
        redirect_uri=redirect_uri,
    )


def _redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/api/v1/auth/oidc/callback"


# ── Benchmarking baseline (admin) ─────────────────────────────────────────────
class BenchmarkSettings(BaseModel):
    enabled: bool = False
    industry: str = Field(default="Industry average", max_length=80)
    baseline_click_rate: float = Field(default=0.0, ge=0, le=100)
    baseline_report_rate: float = Field(default=0.0, ge=0, le=100)


@router.get("/benchmark", response_model=BenchmarkSettings, dependencies=[Depends(require_admin)])
def get_benchmark_settings(db: DbSession = Depends(get_db)) -> BenchmarkSettings:
    def g(key: str, default: str = "") -> str:
        row = db.get(Setting, key)
        return row.value if row is not None and row.value not in (None, "") else default

    def num(key: str) -> float:
        try:
            return float(g(key, "0") or 0)
        except ValueError:
            return 0.0

    return BenchmarkSettings(
        enabled=g("benchmark_enabled", "0") == "1",
        industry=g("benchmark_industry", "Industry average"),
        baseline_click_rate=num("benchmark_click_rate"),
        baseline_report_rate=num("benchmark_report_rate"),
    )


@router.put("/benchmark", response_model=BenchmarkSettings, dependencies=[Depends(require_admin), Depends(csrf_protect)])
def update_benchmark_settings(payload: BenchmarkSettings, db: DbSession = Depends(get_db)) -> BenchmarkSettings:
    _set(db, "benchmark_enabled", "1" if payload.enabled else "0")
    _set(db, "benchmark_industry", payload.industry.strip() or "Industry average")
    _set(db, "benchmark_click_rate", str(payload.baseline_click_rate))
    _set(db, "benchmark_report_rate", str(payload.baseline_report_rate))
    db.commit()
    return get_benchmark_settings(db)


@router.get("/sso", response_model=SsoSettingsOut, dependencies=[Depends(require_admin)])
def get_sso_settings(request: Request, db: DbSession = Depends(get_db)) -> SsoSettingsOut:
    return _sso_out(db, _redirect_uri(request))


@router.put("/sso", response_model=SsoSettingsOut, dependencies=[Depends(require_admin), Depends(csrf_protect)])
def update_sso_settings(payload: SsoSettingsUpdate, request: Request, db: DbSession = Depends(get_db)) -> SsoSettingsOut:
    from ..services.oidc import set_oidc_config

    set_oidc_config(
        db, enabled=payload.enabled, issuer=payload.issuer.strip(), client_id=payload.client_id.strip(),
        client_secret=payload.client_secret, allowed_domains=payload.allowed_domains.strip(),
        auto_provision=payload.auto_provision, button_label=payload.button_label.strip(),
    )
    return _sso_out(db, _redirect_uri(request))
