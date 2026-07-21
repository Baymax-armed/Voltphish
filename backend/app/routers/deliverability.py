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


# ── Allowlist generator ───────────────────────────────────────────────────────
# Getting simulation mail past the org's own filters (without weakening real
# security) is the "quiet" advantage of commercial platforms. We generate the
# exact, scoped allowlist entries for each mail platform so an admin can apply
# them — the safe, filter-preserving path (M365 Advanced Delivery, not a blanket
# IP allow), from the campaign's own sending domains / IPs / tracking URLs.
class AllowlistRequest(BaseModel):
    domains: list[str] = Field(default_factory=list, max_length=50)
    ips: list[str] = Field(default_factory=list, max_length=50)
    urls: list[str] = Field(default_factory=list, max_length=50)


class AllowlistSection(BaseModel):
    platform: str
    where: str
    entries: list[str]
    steps: list[str]
    warning: str | None = None


class AllowlistResult(BaseModel):
    sections: list[AllowlistSection]


def _clean(items: list[str], limit: int) -> list[str]:
    seen: list[str] = []
    for x in items:
        v = (x or "").strip()
        if v and v not in seen:
            seen.append(v)
    return seen[:limit]


@router.post("/allowlist", response_model=AllowlistResult)
def allowlist(payload: AllowlistRequest) -> AllowlistResult:
    domains = _clean(payload.domains, 50)
    ips = _clean(payload.ips, 50)
    urls = _clean(payload.urls, 50)

    sections: list[AllowlistSection] = []

    # Microsoft 365 / Defender — Advanced Delivery (the correct, scoped path).
    m365_entries = []
    if domains:
        m365_entries.append("Sending domains: " + ", ".join(domains))
    if ips:
        m365_entries.append("Sending IPs: " + ", ".join(ips))
    if urls:
        m365_entries.append("Simulation URLs: " + ", ".join(urls))
    sections.append(AllowlistSection(
        platform="Microsoft 365 (Defender)",
        where="Defender portal → Email & Collaboration → Policies & Rules → Threat policies → Advanced delivery → Phishing simulation",
        entries=m365_entries or ["Add your sending domains, IPs, and simulation URLs"],
        steps=[
            "Open the Advanced delivery policy and select the 'Phishing simulation' tab.",
            "Add the sending domains and sending IPs above.",
            "Add the simulation/tracking URLs so Safe Links won't detonate them.",
            "Save — this scopes the bypass to simulations only, keeping filtering intact.",
        ],
        warning="Do NOT use the Connection Filter IP Allow List or Tenant Allow/Block List — those bypass filtering globally and create real security gaps.",
    ))

    # Google Workspace — inbound gateway / spam bypass by sender.
    g_entries = []
    if ips:
        g_entries.append("Inbound gateway IPs: " + ", ".join(ips))
    if domains:
        g_entries.append("Approved senders (domains): " + ", ".join(domains))
    sections.append(AllowlistSection(
        platform="Google Workspace",
        where="Admin console → Apps → Google Workspace → Gmail → Spam, phishing and malware",
        entries=g_entries or ["Add sending IPs to an inbound gateway / approved senders list"],
        steps=[
            "Create or edit an 'Approved senders' list and add the sending domains.",
            "Under 'Inbound gateway', add the sending IPs so SPF/DKIM are evaluated on the original sender.",
            "Optionally add a content-compliance rule to bypass spam for these senders only.",
        ],
        warning="Scope the rule to the specific senders/IPs above — don't disable spam filtering org-wide.",
    ))

    # Generic SEG / mail server.
    generic_entries = []
    if domains:
        generic_entries.append("Envelope-from / header-from domains: " + ", ".join(domains))
    if ips:
        generic_entries.append("Permit sending IPs at the gateway: " + ", ".join(ips))
    if urls:
        generic_entries.append("URL/link scanner exclusions: " + ", ".join(urls))
    sections.append(AllowlistSection(
        platform="Generic gateway / SEG",
        where="Your secure email gateway's allow/permit policy",
        entries=generic_entries or ["Permit the sending IPs and exclude the tracking URLs from rewriting"],
        steps=[
            "Add the sending IPs to the gateway's permitted-senders / connection allow policy.",
            "Exclude the simulation URLs from link rewriting / time-of-click scanning.",
            "If a SEG sits in front of M365/Google, enable Enhanced Filtering so the original IP is evaluated.",
        ],
        warning="Keep entries scoped to the simulation infrastructure and review them after each program.",
    ))

    return AllowlistResult(sections=sections)
