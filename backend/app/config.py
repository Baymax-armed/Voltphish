"""Application configuration, loaded from environment (CLAUDE.md §3, §13).

All settings come from env / .env. No secrets are hardcoded. In production the
app fails to start if the secret key is left at its insecure default.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET = "change-me-generate-a-64-char-random-value"


class Environment(str, Enum):
    development = "development"
    production = "production"


class MailBackend(str, Enum):
    console = "console"
    smtp = "smtp"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PHISHSIM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = Environment.development
    secret_key: str = _INSECURE_SECRET
    database_url: str = "sqlite+pysqlite:///./phishsim.db"

    admin_host: str = "127.0.0.1"
    admin_port: int = 8080
    phish_base_url: str = "http://127.0.0.1:8080"

    cookie_secure: bool = False

    mail_backend: MailBackend = MailBackend.console
    mail_outbox: str = "./outbox"

    # Ethical guardrail (see README "Responsible use"). Default: do NOT store
    # submitted passwords. Only THAT a submission happened is recorded.
    capture_passwords: bool = False

    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = ""

    # If set (e.g. to the bundled Mailpit), a ready-to-use SMTP sending profile
    # is auto-created on first run so email works out of the box for testing.
    dev_smtp_host: str = ""
    dev_smtp_port: int = 1025

    session_ttl_seconds: int = 60 * 60 * 8  # 8h
    login_max_attempts: int = 5
    login_window_seconds: int = 15 * 60

    # AI template generator (optional). Key lives in the environment / secret
    # manager — never in source (CLAUDE.md §3). If unset, the feature is disabled
    # and the endpoint returns a clear "not configured" message.
    ai_api_key: str = ""
    ai_model: str = "claude-sonnet-5"
    ai_base_url: str = "https://api.anthropic.com"

    @property
    def is_production(self) -> bool:
        return self.env is Environment.production

    @field_validator("secret_key")
    @classmethod
    def _secret_must_be_set_in_prod(cls, v: str, info: ValidationInfo) -> str:
        # Fail closed (CLAUDE.md §0.3): a real deployment must not run on the
        # default key. We can't see `env` reliably here (field order), so we
        # re-check in `get_settings()` where the full object exists.
        if len(v) < 16:
            raise ValueError("PHISHSIM_SECRET_KEY must be at least 16 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.secret_key == _INSECURE_SECRET:
        raise RuntimeError(
            "Refusing to start in production with the default PHISHSIM_SECRET_KEY. "
            "Generate one, e.g. `python -c \"import secrets;print(secrets.token_urlsafe(48))\"`."
        )
    if settings.is_production and not settings.cookie_secure:
        raise RuntimeError(
            "Refusing to start in production with PHISHSIM_COOKIE_SECURE=false. "
            "Session cookies must be Secure over HTTPS."
        )
    return settings
