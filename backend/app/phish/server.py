"""Public phishing/tracking endpoints (UNauthenticated by design).

These are the URLs embedded in simulation emails and hit by recipients' browsers:
  GET  /t/{rid}.png  open pixel        -> records email_opened
  GET  /c/{rid}      link click         -> records clicked_link, then redirects
  GET  /p/{rid}      landing page       -> records clicked_link, shows a page
  POST /p/{rid}      landing submission  -> records submitted_data (NO password)
  GET  /r/{rid}      report phish        -> records reported

Security notes:
- These are intentionally public but do NOT trust the rid: unknown/invalid rids
  return a benign response and record nothing (no enumeration signal, A01/A09).
- We NEVER store submitted passwords. By default we don't store any submitted
  field values — only that a submission occurred (see VOLTPHISH_CAPTURE_PASSWORDS).
- No secrets, stack traces, or internal errors are exposed (§7).
"""
from __future__ import annotations

import logging
from base64 import b64decode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..database import get_db
from ..dependencies import client_ip
from ..models import Campaign, EventType, LandingPage, Result
from ..models.base import utcnow
from ..services.adaptive import auto_enroll_on_fail
from ..services.events import record_event
from ..services.qr import qr_png
from ..services.renderer import RenderContext, render_landing
from ..services.tracker import click_url

log = logging.getLogger("voltphish.phish")
settings = get_settings()
router = APIRouter(tags=["phish"], include_in_schema=False)

# 1x1 transparent PNG (served with image/png so clients render + fetch it).
_PIXEL = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

_LANDING_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in</title></head><body style="font-family:system-ui;max-width:22rem;margin:4rem auto">
<h1 style="font-size:1.2rem">Sign in to continue</h1>
<form method="post" autocomplete="off">
<label>Email<br><input name="username" type="email" style="width:100%"></label><br><br>
<label>Password<br><input name="password" type="password" style="width:100%"></label><br><br>
<button type="submit">Sign in</button></form></body></html>"""


def _teaching_html(trained: bool) -> str:
    """The just-in-time training page shown after a recipient falls for a
    simulation. Pure HTML/CSS (no JS) so it renders under the strict CSP. The
    'I understand' button is a form that records the acknowledgment."""
    ack = (
        '<div style="margin-top:26px;padding:14px 18px;background:#e7f6ec;border:1px solid #b6e0c4;'
        'border-radius:8px;color:#1c7a3f;font-weight:600">✓ Thanks — your acknowledgment was recorded.</div>'
        if trained
        else (
            '<form method="post" style="margin-top:26px">'
            '<button type="submit" style="background:#2563eb;color:#fff;border:none;padding:13px 30px;'
            'border-radius:8px;font-size:15px;font-weight:600;cursor:pointer">I understand — I\'ll be more careful</button>'
            "</form>"
        )
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Security awareness</title></head>
<body style="font-family:Segoe UI,system-ui,Arial,sans-serif;background:#f5f6f8;margin:0;color:#1a1a1a">
<div style="max-width:640px;margin:6vh auto;background:#fff;border-radius:14px;box-shadow:0 6px 30px rgba(0,0,0,0.08);overflow:hidden">
  <div style="background:linear-gradient(135deg,#dc2626,#b91c1c);color:#fff;padding:30px 40px">
    <div style="font-size:40px;line-height:1">🎣</div>
    <h1 style="margin:12px 0 4px;font-size:24px">This was a phishing simulation</h1>
    <p style="margin:0;opacity:.9;font-size:15px">Don't worry — no harm done. But a real attacker could have compromised your account. Let's learn what to look for.</p>
  </div>
  <div style="padding:32px 40px">
    <h2 style="font-size:16px;margin:0 0 12px">🚩 Red flags to watch for</h2>
    <ul style="margin:0 0 24px;padding-left:20px;line-height:1.9;font-size:14px;color:#333">
      <li><strong>Urgency &amp; fear</strong> — "act now or your account will be locked."</li>
      <li><strong>Unexpected links or QR codes</strong> — hover to check the real destination first.</li>
      <li><strong>Sender address mismatch</strong> — the display name and the real email domain don't match.</li>
      <li><strong>Requests for credentials</strong> — legitimate IT never asks you to "confirm" your password.</li>
      <li><strong>"Verify you're human" steps</strong> that ask you to paste or run something — never do this.</li>
    </ul>
    <h2 style="font-size:16px;margin:0 0 12px">✅ What to do next time</h2>
    <ul style="margin:0 0 8px;padding-left:20px;line-height:1.9;font-size:14px;color:#333">
      <li>Pause before clicking. When in doubt, don't.</li>
      <li>Report suspicious emails using your mail client's <em>Report Phishing</em> button.</li>
      <li>Verify requests through a known, separate channel (call the person/helpdesk).</li>
    </ul>
    {ack}
  </div>
  <div style="padding:16px 40px;background:#fafafa;border-top:1px solid #eee;font-size:12px;color:#888">
    Security Awareness Training · This exercise was authorized by your security team.
  </div>
</div>
</body></html>"""


def _lookup(db: DbSession, rid: str) -> tuple[Result | None, Campaign | None]:
    result = db.query(Result).filter(Result.rid == rid).one_or_none()
    if result is None:
        return None, None
    return result, db.get(Campaign, result.campaign_id)


def _landing_context(result: Result, campaign: Campaign) -> RenderContext:
    return RenderContext(
        first_name=result.first_name or "",
        last_name=result.last_name or "",
        email=result.email,
        position=result.position or "",
        rid=result.rid,
        phish_url=campaign.phish_url,
    )


def _no_store(resp: Response) -> Response:
    # Aggressively defeat caching/proxying so every open re-registers and mail
    # provider image proxies don't serve a stale copy.
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@router.get("/t/{rid}.png")
def track_open(rid: str, request: Request, db: DbSession = Depends(get_db)) -> Response:
    result, campaign = _lookup(db, rid)
    if result and campaign:
        record_event(
            db,
            campaign_id=campaign.id,
            rid=rid,
            type=EventType.email_opened,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
    # Always return a pixel regardless (don't reveal whether the rid was valid).
    return _no_store(Response(content=_PIXEL, media_type="image/png"))


@router.get("/a/{rid}.png")
def track_attachment(rid: str, request: Request, db: DbSession = Depends(get_db)) -> Response:
    """Pixel embedded in a lure attachment — records that the attachment was opened."""
    result, campaign = _lookup(db, rid)
    if result and campaign:
        if result.attachment_opened_at is None:
            result.attachment_opened_at = utcnow()
        record_event(
            db,
            campaign_id=campaign.id,
            rid=rid,
            type=EventType.email_opened,  # counts as engagement; attachment flag on the result
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
    return _no_store(Response(content=_PIXEL, media_type="image/png"))


@router.get("/q/{rid}.png")
def track_qr(rid: str, db: DbSession = Depends(get_db)) -> Response:
    """Serve the per-recipient QR code (quishing). The QR encodes this
    recipient's click link, so scanning it opens /c/{rid} and records the click.
    Unknown rids get a benign QR to the base URL (no enumeration signal)."""
    result, campaign = _lookup(db, rid)
    if result and campaign:
        target = click_url(campaign.phish_url or settings.phish_base_url, rid)
    else:
        target = settings.phish_base_url
    return _no_store(Response(content=qr_png(target), media_type="image/png"))


@router.get("/s/{code}")
def track_short_click(code: str, request: Request, db: DbSession = Depends(get_db)) -> Response:
    """Short SMS link -> resolve to the recipient and behave like /c/{rid}."""
    result = db.query(Result).filter(Result.short_code == code).one_or_none()
    if result is None:
        return _no_store(RedirectResponse(url=settings.phish_base_url, status_code=302))
    return track_click(result.rid, request, db)


@router.get("/c/{rid}")
def track_click(rid: str, request: Request, db: DbSession = Depends(get_db)) -> Response:
    result, campaign = _lookup(db, rid)
    if not result or not campaign:
        # Benign fallback; no signal that the rid was invalid.
        return _no_store(RedirectResponse(url=settings.phish_base_url, status_code=302))

    record_event(
        db,
        campaign_id=campaign.id,
        rid=rid,
        type=EventType.clicked_link,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    auto_enroll_on_fail(db, result=result, campaign_id=campaign.id, trigger="clicked")

    # If the campaign has a custom landing page, show it (via /p/{rid}).
    # Otherwise honor an explicit redirect_url, else the built-in page.
    if campaign.page_id is None and campaign.redirect_url:
        return _no_store(RedirectResponse(url=campaign.redirect_url, status_code=302))
    # Relative redirect on purpose: stay on whatever host the click actually
    # arrived on (the live tunnel/domain), NOT the campaign's stored phish_url —
    # that may be a different or now-dead tunnel, which would land the recipient
    # on an unreachable host even though the click link itself worked.
    return _no_store(RedirectResponse(url=f"/p/{rid}", status_code=302))


@router.get("/p/{rid}", response_class=HTMLResponse)
def landing_get(rid: str, request: Request, db: DbSession = Depends(get_db)) -> Response:
    result, campaign = _lookup(db, rid)
    if not result or not campaign:
        return _no_store(HTMLResponse(content=_LANDING_HTML))

    record_event(
        db,
        campaign_id=campaign.id,
        rid=rid,
        type=EventType.clicked_link,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

    # Custom landing page if configured, else the built-in awareness page.
    if campaign.page_id is not None:
        page = db.get(LandingPage, campaign.page_id)
        if page is not None:
            html = render_landing(page.html, _landing_context(result, campaign))
            return _no_store(HTMLResponse(content=html))
    return _no_store(HTMLResponse(content=_LANDING_HTML))


@router.post("/p/{rid}", response_class=HTMLResponse)
async def landing_post(rid: str, request: Request, db: DbSession = Depends(get_db)) -> Response:
    result, campaign = _lookup(db, rid)
    if result and campaign:
        # By default store nothing about the submitted values; only that a
        # submission happened (ethical guardrail — the safe default is OFF).
        details: dict | None = None
        if settings.capture_passwords:
            # SECURITY: FULL CAPTURE is on — the operator explicitly opted in
            # (VOLTPHISH_CAPTURE_PASSWORDS=true) to store EVERY submitted field,
            # INCLUDING passwords and other credentials. This creates a store of
            # real secrets: only run it in an AUTHORIZED engagement, restrict and
            # encrypt access, and purge it when done. Values are length-capped.
            form = await request.form()
            details = {
                k: str(v)[:500]
                for k, v in form.items()
                if not hasattr(v, "filename")  # skip file uploads
            } or None
        record_event(
            db,
            campaign_id=campaign.id,
            rid=rid,
            type=EventType.submitted_data,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
            details=details,
        )
        db.commit()
        auto_enroll_on_fail(db, result=result, campaign_id=campaign.id, trigger="submitted")
    # Redirect to the teaching page (awareness moment). Prefer the landing
    # page's own redirect, then the campaign's, then the built-in training page.
    # Default is relative so the teaching page loads on the same host the submit
    # arrived on, not the campaign's stored (possibly stale/dead) phish_url.
    dest = f"/learn/{rid}"
    if campaign:
        page = db.get(LandingPage, campaign.page_id) if campaign.page_id else None
        dest = (page.redirect_url if page and page.redirect_url else None) or (
            campaign.redirect_url or dest
        )
    return _no_store(RedirectResponse(url=dest, status_code=303))


@router.get("/learn/{rid}", response_class=HTMLResponse)
def learn_get(rid: str, db: DbSession = Depends(get_db)) -> Response:
    """Just-in-time training page shown after a recipient falls for a sim."""
    result, campaign = _lookup(db, rid)
    trained = bool(result and result.trained_at)
    return _no_store(HTMLResponse(content=_teaching_html(trained)))


@router.post("/learn/{rid}", response_class=HTMLResponse)
def learn_ack(rid: str, db: DbSession = Depends(get_db)) -> Response:
    """Record that the recipient acknowledged the training ('I understand')."""
    result, campaign = _lookup(db, rid)
    if result and result.trained_at is None:
        result.trained_at = utcnow()
        db.commit()
    return _no_store(HTMLResponse(content=_teaching_html(True)))


def _record_report(rid: str, request: Request, db: DbSession) -> Response:
    result, campaign = _lookup(db, rid)
    if result and campaign:
        record_event(
            db,
            campaign_id=campaign.id,
            rid=rid,
            type=EventType.reported,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
    return _no_store(HTMLResponse(content="<p>Thanks for reporting this message.</p>"))


@router.get("/r/{rid}")
def report_phish(rid: str, request: Request, db: DbSession = Depends(get_db)) -> Response:
    return _record_report(rid, request, db)


@router.get("/report")
def report_phish_query(rid: str, request: Request, db: DbSession = Depends(get_db)) -> Response:
    """Gophish-compatible report endpoint: GET /report?rid=... — lets a mail-client
    'report phishing' button/extension mark a recipient as having reported."""
    return _record_report(rid, request, db)
