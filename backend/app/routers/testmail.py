"""Send a single test email to verify a Sending Profile + Template render and
deliver correctly. Authenticated; CSRF-protected."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user
from ..models import SendingProfile, Template
from ..schemas.common import Message
from ..schemas.testmail import TestEmailRequest
from ..security import new_result_id
from ..services.handlers import build_attachments
from ..services.mailer import OutgoingEmail, friendly_smtp_error, profile_headers, send_email
from ..services.renderer import RenderContext, render_html, render_subject, render_text

log = logging.getLogger("voltphish.testmail")
settings = get_settings()

router = APIRouter(
    prefix="/api/v1/test",
    tags=["test"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect)],
)


@router.post("/email", response_model=Message)
async def send_test_email(payload: TestEmailRequest, db: DbSession = Depends(get_db)) -> Message:
    profile = db.get(SendingProfile, payload.profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "profile_id does not exist")
    template = db.get(Template, payload.template_id)
    if template is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "template_id does not exist")

    # A throwaway rid: tracking links resolve but match no Result (benign).
    ctx = RenderContext(
        first_name=payload.first_name or "Test",
        last_name=payload.last_name or "User",
        email=payload.to_email,
        position=payload.position or "",
        rid=new_result_id(),
        phish_url=settings.phish_base_url,
    )
    subject = "[TEST] " + render_subject(template.subject, ctx)
    html = render_html(template.html, ctx) if template.html else None
    text = render_text(template.text, ctx) if template.text else None

    try:
        # allow_console=False: a test email must exercise the REAL SMTP server,
        # even when the app is running in console/dev mode — otherwise the test
        # would fake success and tell you nothing about your credentials.
        await send_email(
            OutgoingEmail(
                to_address=str(payload.to_email),
                from_address=template.envelope_sender or profile.from_address,
                subject=subject,
                html=html,
                text=text,
                envelope_from=profile.envelope_sender,
                extra_headers=profile_headers(profile),
                attachments=build_attachments(template),
            ),
            profile,
            allow_console=False,
        )
    except Exception as exc:  # noqa: BLE001
        # Full detail to logs; a clear, actionable reason to the operator.
        log.exception("test email failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Send failed: {friendly_smtp_error(exc)}")

    return Message(detail=f"Test email actually sent to {payload.to_email} via SMTP ({profile.host}:{profile.port}).")
