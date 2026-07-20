"""Email template CRUD. All routes require authentication (A01)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

import base64
import binascii
from pathlib import PurePath

from ..database import get_db
from ..csrf import csrf_protect
from ..dependencies import get_current_user
from ..models import Attachment, Template, User
from ..schemas.common import Message
from ..schemas.template import (
    AiGenerateRequest,
    AiGenerateResult,
    AttachmentCreate,
    AttachmentOut,
    TemplateCreate,
    TemplateImportRequest,
    TemplateImportResult,
    TemplateOut,
    TemplateUpdate,
)
from ..services.ai import AiError, generate_template, get_ai_config
from ..services.mimeimport import parse_email

# Guardrails: benign lure document types only — no executables/scripts.
_ALLOWED_EXT = {
    ".pdf", ".doc", ".docx", ".docm", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx",
    ".txt", ".csv", ".html", ".htm", ".ics", ".png", ".jpg", ".jpeg", ".gif", ".zip",
}
_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024      # 5 MB per file
_MAX_TEMPLATE_ATTACH_BYTES = 15 * 1024 * 1024  # 15 MB total per template

router = APIRouter(
    prefix="/api/v1/templates",
    tags=["templates"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect)],
)


@router.get("", response_model=list[TemplateOut])
def list_templates(db: DbSession = Depends(get_db)) -> list[Template]:
    return list(db.execute(select(Template).order_by(Template.name)).scalars())


@router.post("/import", response_model=TemplateImportResult)
def import_template(payload: TemplateImportRequest) -> TemplateImportResult:
    """Parse a pasted raw email into fields (does not save it)."""
    return TemplateImportResult(**parse_email(payload.raw))


@router.post("/ai-generate", response_model=AiGenerateResult)
async def ai_generate(payload: AiGenerateRequest, db: DbSession = Depends(get_db)) -> AiGenerateResult:
    """Draft a simulation email from a scenario using the configured LLM.
    Does not save it — the operator reviews and edits before saving."""
    cfg = get_ai_config(db)
    try:
        result = await generate_template(
            payload.scenario, payload.difficulty,
            provider=cfg["provider"], api_key=cfg["api_key"], model=cfg["model"], base_url=cfg["base_url"],
        )
    except AiError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return AiGenerateResult(**result)


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(payload: TemplateCreate, db: DbSession = Depends(get_db)) -> Template:
    tpl = Template(**payload.model_dump())
    db.add(tpl)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A template with that name already exists")
    db.refresh(tpl)
    return tpl


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(template_id: int, db: DbSession = Depends(get_db)) -> Template:
    tpl = db.get(Template, template_id)
    if tpl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return tpl


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: int, payload: TemplateUpdate, db: DbSession = Depends(get_db)
) -> Template:
    tpl = db.get(Template, template_id)
    if tpl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    for k, v in payload.model_dump().items():
        setattr(tpl, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A template with that name already exists")
    db.refresh(tpl)
    return tpl


@router.get("/{template_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(template_id: int, db: DbSession = Depends(get_db)) -> list[Attachment]:
    tpl = db.get(Template, template_id)
    if tpl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return tpl.attachments


@router.post("/{template_id}/attachments", response_model=AttachmentOut, status_code=201)
def add_attachment(
    template_id: int, payload: AttachmentCreate, db: DbSession = Depends(get_db)
) -> Attachment:
    tpl = db.get(Template, template_id)
    if tpl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")

    filename = PurePath(payload.filename).name  # strip any path components
    ext = PurePath(filename).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"File type '{ext or '(none)'}' not allowed. Allowed: {', '.join(sorted(_ALLOWED_EXT))}",
        )
    try:
        raw = base64.b64decode(payload.content_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "content_b64 is not valid base64")
    if len(raw) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "attachment is empty")
    if len(raw) > _MAX_ATTACHMENT_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "attachment exceeds 5 MB limit")
    if sum(a.size for a in tpl.attachments) + len(raw) > _MAX_TEMPLATE_ATTACH_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "total attachments exceed 15 MB limit")

    att = Attachment(
        template_id=tpl.id,
        filename=filename,
        content_type=payload.content_type,
        content_b64=payload.content_b64,
        size=len(raw),
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


@router.delete("/{template_id}/attachments/{attachment_id}", response_model=Message)
def delete_attachment(
    template_id: int, attachment_id: int, db: DbSession = Depends(get_db)
) -> Message:
    att = db.get(Attachment, attachment_id)
    if att is None or att.template_id != template_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    db.delete(att)
    db.commit()
    return Message(detail="Attachment deleted")


@router.delete("/{template_id}", response_model=Message)
def delete_template(
    template_id: int, db: DbSession = Depends(get_db), _: User = Depends(get_current_user)
) -> Message:
    tpl = db.get(Template, template_id)
    if tpl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    db.delete(tpl)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This template is still used by a campaign — delete those campaigns first.")
    return Message(detail="Template deleted")
