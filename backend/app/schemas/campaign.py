from __future__ import annotations

from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator

from ..models import CampaignStatus, ResultStatus


class LaunchRequest(BaseModel):
    # Operator must attest authorized scope before a campaign sends (governance).
    authorized: bool = False
    authorization_ref: str | None = Field(default=None, max_length=500)


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    template_id: int
    profile_id: int | None = None
    group_id: int
    page_id: int | None = None
    phish_url: AnyHttpUrl
    redirect_url: AnyHttpUrl | None = None
    launch_at: datetime | None = None
    # Optional drip window end: messages are spread across [launch_at, send_by_at].
    send_by_at: datetime | None = None

    @model_validator(mode="after")
    def _check(self) -> "CampaignCreate":
        if self.profile_id is None:
            raise ValueError("profile_id is required")
        if self.send_by_at is not None and self.launch_at is not None and self.send_by_at <= self.launch_at:
            raise ValueError("send_by_at must be after launch_at")
        return self


class ResultOut(BaseModel):
    id: int
    rid: str
    short_code: str | None
    email: str
    phone: str | None
    first_name: str | None
    last_name: str | None
    position: str | None
    status: ResultStatus
    send_error: str | None
    sent_at: datetime | None
    last_event_at: datetime | None
    attachment_opened_at: datetime | None = None
    model_config = {"from_attributes": True}


class CampaignOut(BaseModel):
    id: int
    name: str
    status: CampaignStatus
    channel: str
    template_id: int
    profile_id: int | None
    group_id: int
    page_id: int | None
    phish_url: str
    redirect_url: str | None
    authorized_by: str | None = None
    authorization_ref: str | None = None
    created_at: datetime
    launch_at: datetime | None
    send_by_at: datetime | None
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class CampaignStats(BaseModel):
    total: int
    sent: int
    opened: int
    clicked: int
    submitted: int
    reported: int
    error: int
    attachments_opened: int = 0


class CampaignDetail(CampaignOut):
    stats: CampaignStats
    results: list[ResultOut]


class EventOut(BaseModel):
    id: int
    rid: str | None
    type: str
    ip: str | None
    created_at: datetime
    model_config = {"from_attributes": True}
