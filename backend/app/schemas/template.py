from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class AttachmentOut(BaseModel):
    id: int
    filename: str
    content_type: str
    size: int
    model_config = {"from_attributes": True}


class AttachmentCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=200)
    # Base64-encoded file bytes.
    content_b64: str = Field(min_length=1, max_length=15_000_000)


class TemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    channel: str = Field(default="email", pattern="^email$")
    subject: str = Field(default="", max_length=500)
    envelope_sender: EmailStr | None = None
    html: str | None = Field(default=None, max_length=1_000_000)
    text: str | None = Field(default=None, max_length=1_000_000)

    @model_validator(mode="after")
    def _need_a_body(self) -> "TemplateBase":
        if not self.subject:
            raise ValueError("email template needs a subject")
        if not (self.html or self.text):
            raise ValueError("email template must have html and/or text body")
        return self


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(TemplateBase):
    pass


class TemplateOut(TemplateBase):
    id: int
    created_at: datetime
    modified_at: datetime
    attachments: list[AttachmentOut] = []
    model_config = {"from_attributes": True}


class TemplateImportRequest(BaseModel):
    raw: str = Field(min_length=1, max_length=2_000_000)


class TemplateImportResult(BaseModel):
    subject: str
    envelope_sender: str | None = None
    html: str | None = None
    text: str | None = None


class AiGenerateRequest(BaseModel):
    scenario: str = Field(min_length=4, max_length=2000)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class AiGenerateResult(BaseModel):
    name: str
    subject: str
    html: str | None = None
    text: str | None = None
