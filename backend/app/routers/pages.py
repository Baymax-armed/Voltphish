"""Landing page CRUD. All routes require authentication (A01)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from ..csrf import csrf_protect
from ..database import get_db
from ..dependencies import get_current_user
from ..models import LandingPage
from ..schemas.common import Message
from ..schemas.page import (
    PageCreate,
    PageOut,
    PageSummary,
    PageUpdate,
    SiteImportRequest,
    SiteImportResult,
)
from ..services.siteimport import SiteImportError, fetch_site
from ..services.ssrf import SsrfError

router = APIRouter(
    prefix="/api/v1/pages",
    tags=["pages"],
    dependencies=[Depends(get_current_user), Depends(csrf_protect)],
)


@router.get("", response_model=list[PageSummary])
def list_pages(db: DbSession = Depends(get_db)) -> list[LandingPage]:
    return list(db.execute(select(LandingPage).order_by(LandingPage.name)).scalars())


@router.post("/import-site", response_model=SiteImportResult)
def import_site(payload: SiteImportRequest) -> SiteImportResult:
    """Fetch a URL and return its HTML to seed a landing page (SSRF-guarded)."""
    try:
        result = fetch_site(str(payload.url))
    except (SiteImportError, SsrfError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return SiteImportResult(**result)


@router.post("", response_model=PageOut, status_code=status.HTTP_201_CREATED)
def create_page(payload: PageCreate, db: DbSession = Depends(get_db)) -> LandingPage:
    page = LandingPage(
        name=payload.name,
        html=payload.html,
        redirect_url=str(payload.redirect_url) if payload.redirect_url else None,
    )
    db.add(page)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A page with that name already exists")
    db.refresh(page)
    return page


@router.get("/{page_id}", response_model=PageOut)
def get_page(page_id: int, db: DbSession = Depends(get_db)) -> LandingPage:
    page = db.get(LandingPage, page_id)
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    return page


@router.put("/{page_id}", response_model=PageOut)
def update_page(page_id: int, payload: PageUpdate, db: DbSession = Depends(get_db)) -> LandingPage:
    page = db.get(LandingPage, page_id)
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    page.name = payload.name
    page.html = payload.html
    page.redirect_url = str(payload.redirect_url) if payload.redirect_url else None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A page with that name already exists")
    db.refresh(page)
    return page


@router.delete("/{page_id}", response_model=Message)
def delete_page(page_id: int, db: DbSession = Depends(get_db)) -> Message:
    page = db.get(LandingPage, page_id)
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    db.delete(page)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This landing page is still used by a campaign — delete those campaigns first.")
    return Message(detail="Page deleted")
