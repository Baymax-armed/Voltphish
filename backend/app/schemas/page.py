from __future__ import annotations

from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field


class PageBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    html: str = Field(min_length=1, max_length=2_000_000)
    redirect_url: AnyHttpUrl | None = None


class PageCreate(PageBase):
    pass


class PageUpdate(PageBase):
    pass


class PageOut(BaseModel):
    id: int
    name: str
    html: str
    redirect_url: str | None
    created_at: datetime
    modified_at: datetime
    model_config = {"from_attributes": True}


class PageSummary(BaseModel):
    id: int
    name: str
    redirect_url: str | None
    modified_at: datetime
    model_config = {"from_attributes": True}


class SiteImportRequest(BaseModel):
    url: AnyHttpUrl


class SiteImportResult(BaseModel):
    url: str
    html: str


class AiPageRequest(BaseModel):
    scenario: str = Field(min_length=4, max_length=2000)


class AiPageResult(BaseModel):
    name: str
    html: str
