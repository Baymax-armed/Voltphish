"""Campaign CRUD, launch, and results. All routes require authentication (A01)."""
from __future__ import annotations

import csv
import io
import logging

log = logging.getLogger("voltphish.campaigns")

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
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
    Target,
    Template,
    TrainingModule,
    User,
    utcnow,
)
from ..services.audience import OUTCOMES, campaign_recipient_targets, campaign_results
from ..schemas.campaign import (
    CampaignCreate,
    CampaignDetail,
    CampaignOut,
    CampaignStats,
    EventOut,
    LaunchRequest,
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
        target_group_ids=campaign.target_group_ids,
        exclude_group_ids=campaign.exclude_group_ids,
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
    if db.get(SendingProfile, payload.profile_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "profile_id does not exist")

    # NG-001: resolve the include/exclude group sets (group_ids falls back to
    # the single group_id for backward compatibility).
    target_ids = payload.group_ids or [payload.group_id]
    target_groups = [db.get(Group, gid) for gid in dict.fromkeys(target_ids)]
    if any(g is None for g in target_groups):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "a target group does not exist")
    exclude_groups = [db.get(Group, gid) for gid in dict.fromkeys(payload.exclude_group_ids)]
    if any(g is None for g in exclude_groups):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "an exclusion group does not exist")

    if payload.page_id is not None and db.get(LandingPage, payload.page_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "page_id does not exist")
    if payload.auto_enroll_trigger != "off" and payload.auto_enroll_module_id is not None:
        if db.get(TrainingModule, payload.auto_enroll_module_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "auto_enroll_module_id does not exist")

    # A future launch date schedules the campaign; the background scheduler
    # picks it up when due. No launch date = a manual-launch draft.
    scheduled = payload.launch_at is not None and payload.launch_at > utcnow()
    campaign = Campaign(
        name=payload.name,
        channel="email",
        template_id=payload.template_id,
        profile_id=payload.profile_id,
        group_id=target_groups[0].id,  # primary group = first target
        page_id=payload.page_id,
        phish_url=str(payload.phish_url),
        redirect_url=str(payload.redirect_url) if payload.redirect_url else None,
        launch_at=payload.launch_at,
        send_by_at=payload.send_by_at,
        send_jitter=payload.send_jitter,
        business_hours_only=payload.business_hours_only,
        send_timezone=payload.send_timezone,
        auto_enroll_trigger=payload.auto_enroll_trigger,
        auto_enroll_module_id=payload.auto_enroll_module_id if payload.auto_enroll_trigger != "off" else None,
        auto_enroll_email=payload.auto_enroll_email,
        status=CampaignStatus.scheduled if scheduled else CampaignStatus.draft,
    )
    campaign.target_groups = target_groups
    campaign.exclude_groups = exclude_groups
    # There must be someone left to send to after dedupe + exclusion.
    if not campaign_recipient_targets(campaign):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No recipients — the target groups are empty or everyone is excluded.",
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


class RecipientPreviewIn(BaseModel):
    group_ids: list[int] = Field(default_factory=list)
    exclude_group_ids: list[int] = Field(default_factory=list)


class RecipientPreviewOut(BaseModel):
    count: int       # final recipients, after dedupe + exclusion
    unique: int      # unique emails across the target groups (before exclusion)
    excluded: int    # how many were removed by the exclusion groups
    duplicates: int  # duplicate memberships collapsed by dedupe


@router.post("/preview-recipients", response_model=RecipientPreviewOut)
def preview_recipients(payload: RecipientPreviewIn, db: DbSession = Depends(get_db)) -> RecipientPreviewOut:
    """Live 'X recipients (Y excluded, Z dupes removed)' count for the campaign
    form, without creating anything."""
    include = [db.get(Group, gid) for gid in dict.fromkeys(payload.group_ids)]
    if any(g is None for g in include):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "a target group does not exist")
    exclude = [db.get(Group, gid) for gid in dict.fromkeys(payload.exclude_group_ids)]
    if any(g is None for g in exclude):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "an exclusion group does not exist")

    raw = 0
    unique: set[str] = set()
    for g in include:
        for t in g.targets:
            if t.email:
                raw += 1
                unique.add(t.email.strip().lower())
    excluded_emails: set[str] = set()
    for g in exclude:
        for t in g.targets:
            if t.email:
                excluded_emails.add(t.email.strip().lower())

    final = unique - excluded_emails
    return RecipientPreviewOut(
        count=len(final), unique=len(unique),
        excluded=len(unique & excluded_emails), duplicates=raw - len(unique),
    )


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
async def launch_campaign(
    campaign_id: int,
    payload: LaunchRequest | None = None,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignDetail:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    if campaign.status not in (CampaignStatus.draft, CampaignStatus.scheduled):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Campaign cannot be launched from status '{campaign.status.value}'",
        )

    # Governance gate (CLAUDE.md §9 audit; "Responsible use"): the operator must
    # attest they're authorized to test these recipients. We record who launched
    # and the authorization reference in an append-only audit event.
    payload = payload or LaunchRequest()
    if not payload.authorized:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You must confirm you are authorized to test these recipients before launching.",
        )
    campaign.authorized_by = user.email
    campaign.authorization_ref = (payload.authorization_ref or "").strip()[:500] or None
    campaign.launch_at = campaign.launch_at or utcnow()

    record_event(
        db, campaign_id=campaign.id, rid=None, type=EventType.campaign_launched,
        details={"by": user.email, "authorization_ref": campaign.authorization_ref},
    )
    # Enqueue durable per-recipient send jobs; the queue workers deliver them
    # (restart-safe, multi-worker-safe).
    enqueue_campaign(db, campaign)
    db.commit()
    db.refresh(campaign)
    log.info("campaign %s launched by %s (auth_ref=%r)", campaign.id, user.email, campaign.authorization_ref)
    return _detail(campaign)


class SaveGroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    outcome: str = "clicked"  # all | clicked | submitted | opened | reported | no_action


class SaveGroupOut(BaseModel):
    group_id: int
    name: str
    added: int


@router.post("/{campaign_id}/save-group", response_model=SaveGroupOut, status_code=status.HTTP_201_CREATED)
def save_audience_as_group(
    campaign_id: int, payload: SaveGroupIn, db: DbSession = Depends(get_db)
) -> SaveGroupOut:
    """Snapshot the recipients of a campaign (optionally just those who failed a
    given way) into a reusable group, so the same people can be re-tested."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    if payload.outcome not in OUTCOMES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown outcome filter")

    name = payload.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Group name is required")

    # Dedupe by lowercased email, keeping one snapshot per person (their name at
    # send time — targets may have changed since).
    seen: dict[str, object] = {}
    for r in campaign_results(db, campaign_id, payload.outcome):
        key = (r.email or "").strip().lower()
        if key and key not in seen:
            seen[key] = r
    if not seen:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No recipients match that outcome")

    group = Group(name=name)
    db.add(group)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A group with that name already exists")

    for key, r in seen.items():
        db.add(Target(
            group_id=group.id, email=key,
            first_name=r.first_name, last_name=r.last_name, position=r.position,
        ))
    db.commit()
    return SaveGroupOut(group_id=group.id, name=name, added=len(seen))


@router.delete("/{campaign_id}", response_model=Message)
def delete_campaign(campaign_id: int, db: DbSession = Depends(get_db)) -> Message:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    db.delete(campaign)
    db.commit()
    return Message(detail="Campaign deleted")
