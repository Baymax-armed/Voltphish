from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

ApiProvider = Literal["sendgrid", "brevo", "resend", "mailgun", "postmark"]


class HeaderItem(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(max_length=1000)

    @field_validator("key", "value")
    @classmethod
    def _no_crlf(cls, v: str) -> str:
        # Prevent SMTP header injection (A03).
        if "\r" in v or "\n" in v:
            raise ValueError("header values must not contain CR/LF")
        return v


class ProfileBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    from_address: EmailStr
    # Envelope sender (Return-Path) for SPF; optional. If set, the recipient can
    # see a spoofed `from_address` while SPF checks this authorized address.
    envelope_sender: EmailStr | None = None
    kind: Literal["smtp", "api"] = "smtp"

    # SMTP fields (required only when kind == "smtp").
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=587, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    headers: list[HeaderItem] = Field(default_factory=list, max_length=50)
    use_starttls: bool = True
    use_ssl: bool = False
    ignore_cert_errors: bool = False

    # API fields (required only when kind == "api").
    api_provider: ApiProvider | None = None
    api_domain: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _require_by_kind(self) -> "ProfileBase":
        if self.kind == "smtp":
            if not self.host:
                raise ValueError("host is required for an SMTP profile")
        else:  # api
            if not self.api_provider:
                raise ValueError("api_provider is required for an API profile")
            if self.api_provider == "mailgun" and not self.api_domain:
                raise ValueError("Mailgun requires a sending domain (api_domain)")
        return self


class ProfileCreate(ProfileBase):
    password: str | None = Field(default=None, max_length=1024)  # SMTP, write-only
    api_key: str | None = Field(default=None, max_length=1024)   # API, write-only

    @model_validator(mode="after")
    def _api_key_on_create(self) -> "ProfileCreate":
        if self.kind == "api" and not self.api_key:
            raise ValueError("api_key is required when creating an API profile")
        return self


class ProfileUpdate(ProfileBase):
    # None => keep existing; "" => clear; value => replace.
    password: str | None = Field(default=None, max_length=1024)
    api_key: str | None = Field(default=None, max_length=1024)


class ProfileOut(ProfileBase):
    id: int
    has_password: bool
    has_api_key: bool
    created_at: datetime
    modified_at: datetime
    model_config = {"from_attributes": True}
