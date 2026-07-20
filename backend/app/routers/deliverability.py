"""Deliverability pre-flight check (SPF/DKIM/DMARC). Authenticated; read-only DNS."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import get_current_user
from ..services.deliverability import DeliverabilityError, check_domain

router = APIRouter(
    prefix="/api/v1/deliverability",
    tags=["deliverability"],
    dependencies=[Depends(get_current_user)],
)


class CheckRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=253)
    selector: str | None = Field(default=None, max_length=63)


class CheckItem(BaseModel):
    key: str
    label: str
    status: str
    record: str | None = None
    note: str


class CheckResult(BaseModel):
    domain: str
    verdict: str
    summary: str
    passed: int
    checks: list[CheckItem]


@router.post("/check", response_model=CheckResult)
def check(payload: CheckRequest) -> CheckResult:
    try:
        result = check_domain(payload.domain, payload.selector)
    except DeliverabilityError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return CheckResult(**result)
