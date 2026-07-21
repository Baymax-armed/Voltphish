"""Campaign CRUD, launch, and results. All routes require authentication (A01)."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..csrf import csrf_protect
from ..dependencies import get_current_user
from ..models import (
    Campaign,
    CampaignStatus,
    EventType,
    Group,
    LandingPage,
    ResultStatus,
    SendingProfile,
    SmsProfile,
    Template,
    utcnow,
)
from ..schemas.campaign import (
    CampaignCreate,
    CampaignDetail,
    CampaignOut,
    CampaignStats,
    EventOut,
    ResultOut,
)
from ..schemas.common import Message
from ..services.events import record_event
from ..services.sender import enqueue_campaign

router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["campaigns"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect)],
)


def _stats(campaign: Campaign) -> CampaignStats:
    counts = {s: 0 for s in ResultStatus}
    for r in campaign.results:
        counts[r.status] += 1
    # A recipient who clicked also "opened"; report cumulative funnel numbers.
    total = len(campaign.results)
    sent = total - counts[ResultStatus.scheduled] - counts[ResultStatus.sending]
    opened = (
        counts[ResultStatus.opened]
        + counts[ResultStatus.clicked]
        + counts[ResultStatus.submitted]
    )
    clicked = counts[ResultStatus.clicked] + counts[ResultStatus.submitted]
    return CampaignStats(
        total=total,
        sent=sent - counts[ResultStatus.error] if sent >= counts[ResultStatus.error] else sent,
        opened=opened,
        clicked=clicked,
        submitted=counts[ResultStatus.submitted],
        reported=counts[ResultStatus.reported],
        error=counts[ResultStatus.error],
        attachments_opened=sum(1 for r in campaign.results if r.attachment_opened_at is not None),
    )


def _detail(campaign: Campaign) -> CampaignDetail:
    return CampaignDetail(
        **CampaignOut.model_validate(campaign).model_dump(),
        stats=_stats(campaign),
        results=[ResultOut.model_validate(r) for r in campaign.results],
    )


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: DbSession = Depends(get_db)) -> list[Campaign]:
    return list(db.execute(select(Campaign).order_by(Campaign.created_at.desc())).scalars())


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, db: DbSession = Depends(get_db)) -> Campaign:
    # Validate all foreign references exist (fail with a clear 400, not a 500).
    template = db.get(Template, payload.template_id)
    if template is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "template_id does not exist")
    if template.channel != payload.channel:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"template is not a {payload.channel} template")
    if payload.channel == "sms":
        if db.get(SmsProfile, payload.sms_profile_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "sms_profile_id does not exist")
    else:
        if db.get(SendingProfile, payload.profile_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "profile_id does not exist")
    group = db.get(Group, payload.group_id)
    if group is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "group_id does not exist")
    if not group.targets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "group has no targets")
    if payload.channel == "sms" and not any(t.phone for t in group.targets):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "SMS campaign needs targets with phone numbers")
    if payload.page_id is not None and db.get(LandingPage, payload.page_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "page_id does not exist")

    # A future launch date schedules the campaign; the background scheduler
    # picks it up when due. No launch date = a manual-launch draft.
    scheduled = payload.launch_at is not None and payload.launch_at > utcnow()
    campaign = Campaign(
        name=payload.name,
        channel=payload.channel,
        template_id=payload.template_id,
        profile_id=payload.profile_id if payload.channel == "email" else None,
        sms_profile_id=payload.sms_profile_id if payload.channel == "sms" else None,
        group_id=payload.group_id,
        page_id=payload.page_id,
        phish_url=str(payload.phish_url),
        redirect_url=str(payload.redirect_url) if payload.redirect_url else None,
        launch_at=payload.launch_at,
        send_by_at=payload.send_by_at,
        status=CampaignStatus.scheduled if scheduled else CampaignStatus.draft,
    )
    db.add(campaign)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A campaign with that name already exists")
    db.refresh(campaign)
    record_event(db, campaign_id=campaign.id, rid=None, type=EventType.campaign_created)
    db.commit()
    return campaign


@router.get("/{campaign_id}", response_model=CampaignDetail)
def get_campaign(campaign_id: int, db: DbSession = Depends(get_db)) -> CampaignDetail:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return _detail(campaign)


@router.get("/{campaign_id}/events", response_model=list[EventOut])
def get_campaign_events(campaign_id: int, db: DbSession = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return sorted(campaign.events, key=lambda e: e.created_at)


def _csv_safe(value: object) -> str:
    """Neutralize CSV/spreadsheet formula injection: a cell beginning with
    = + - @ (or a control char) is prefixed with a quote so Excel/Sheets treats
    it as text, not a formula (target names/emails are user-influenced)."""
    s = "" if value is None else str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


@router.get("/{campaign_id}/results.csv")
def export_results_csv(campaign_id: int, db: DbSession = Depends(get_db)) -> StreamingResponse:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["email", "first_name", "last_name", "position", "status", "send_error",
         "sent_at", "last_event_at", "rid"]
    )
    for r in campaign.results:
        writer.writerow(
            [_csv_safe(r.email), _csv_safe(r.first_name), _csv_safe(r.last_name),
             _csv_safe(r.position), r.status.value, _csv_safe(r.send_error),
             r.sent_at.isoformat() if r.sent_at else "",
             r.last_event_at.isoformat() if r.last_event_at else "", r.rid]
        )
    buf.seek(0)
    filename = f"campaign-{campaign_id}-results.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{campaign_id}/launch", response_model=CampaignDetail)
async def launch_campaign(campaign_id: int, db: DbSession = Depends(get_db)) -> CampaignDetail:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    if campaign.status not in (CampaignStatus.draft, CampaignStatus.scheduled):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Campaign cannot be launched from status '{campaign.status.value}'",
        )

    campaign.launch_at = campaign.launch_at or utcnow()
    # Enqueue durable per-recipient send jobs; the queue workers deliver them
    # (restart-safe, multi-worker-safe).
    enqueue_campaign(db, campaign)
    db.commit()
    db.refresh(campaign)
    return _detail(campaign)


@router.delete("/{campaign_id}", response_model=Message)
def delete_campaign(campaign_id: int, db: DbSession = Depends(get_db)) -> Message:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    db.delete(campaign)
    db.commit()
    return Message(detail="Campaign deleted")
