"""Safe personalization-token rendering for email bodies.

We deliberately DO NOT use a full template engine on operator-authored bodies:
plain token substitution avoids server-side template injection (CLAUDE.md A03).

Supported tokens (Gophish-compatible subset):
  {{.FirstName}} {{.LastName}} {{.Email}} {{.Position}}
  {{.URL}}         click-tracking link (records click, then redirects)
  {{.TrackingURL}} open-tracking pixel URL
  {{.Tracker}}     a ready-made <img> pixel tag
  {{.QR}}          a ready-made <img> QR code that opens the click link (quishing)
  {{.QRURL}}       the QR-code image URL (for custom sizing/markup)
  {{.RId}}         the raw result id

Recipient-supplied values (name/position/email) are HTML-escaped when rendering
an HTML body so a crafted target name can't inject markup (context-aware output
encoding, A03). URLs we generate ourselves are trusted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape

from . import tracker


@dataclass(frozen=True)
class RenderContext:
    first_name: str
    last_name: str
    email: str
    position: str
    rid: str
    phish_url: str
    short_code: str = ""


def _pixel_tag(url: str) -> str:
    # Avoid display:none — several mail clients skip loading hidden images,
    # which would defeat open tracking. A 1x1 image is effectively invisible.
    return (
        f'<img src="{escape(url, quote=True)}" alt="" width="1" height="1" '
        'border="0" style="width:1px;height:1px;border:0;opacity:0" />'
    )


def _qr_tag(url: str) -> str:
    # A visible, scannable QR built from HTML table cells rather than an <img>,
    # so it still renders when the mail client blocks images from an unverified
    # sender (Outlook does this by default). Encodes the tracked click link, so a
    # phone-camera scan opens the landing page exactly like a real quishing lure.
    from .qr import qr_html_table

    return qr_html_table(url)


def _substitute(body: str, ctx: RenderContext, *, is_html: bool) -> str:
    enc = (lambda s: escape(s or "")) if is_html else (lambda s: s or "")
    click = tracker.click_url(ctx.phish_url, ctx.rid)
    pixel = tracker.open_pixel_url(ctx.phish_url, ctx.rid)
    qr = tracker.qr_url(ctx.phish_url, ctx.rid)

    replacements = {
        "{{.FirstName}}": enc(ctx.first_name),
        "{{.LastName}}": enc(ctx.last_name),
        "{{.Email}}": enc(ctx.email),
        "{{.Position}}": enc(ctx.position),
        "{{.RId}}": ctx.rid,
        "{{.URL}}": click,           # our own URL; safe to inline
        "{{.TrackingURL}}": pixel,
        "{{.Tracker}}": _pixel_tag(pixel) if is_html else "",
        "{{.QRURL}}": qr,            # PNG-serving endpoint, for custom <img> markup
        # Ready-made QR: a table encoding the click link (image-blocking-proof).
        # Scanning it opens the tracked landing page. Text emails get the URL.
        "{{.QR}}": _qr_tag(click) if is_html else click,
        "{{.AttachURL}}": tracker.attach_pixel_url(ctx.phish_url, ctx.rid),
        # Always a real <img> pixel so it fires from inside an HTML attachment.
        "{{.AttachTracker}}": _pixel_tag(tracker.attach_pixel_url(ctx.phish_url, ctx.rid)),
    }
    for token, value in replacements.items():
        body = body.replace(token, value)
    return body


def render_html(body: str, ctx: RenderContext) -> str:
    out = _substitute(body, ctx, is_html=True)
    # Ensure an open-tracking pixel exists even if the author didn't add one.
    if "{{.Tracker}}" not in body and "{{.TrackingURL}}" not in body:
        pixel = _pixel_tag(tracker.open_pixel_url(ctx.phish_url, ctx.rid))
        if "</body>" in out.lower():
            idx = out.lower().rfind("</body>")
            out = out[:idx] + pixel + out[idx:]
        else:
            out = out + pixel
    return out


def render_text(body: str, ctx: RenderContext) -> str:
    return _substitute(body, ctx, is_html=False)


def render_subject(subject: str, ctx: RenderContext) -> str:
    # Subjects are header values: substitute, then strip CR/LF to prevent
    # header injection (A03).
    rendered = _substitute(subject, ctx, is_html=False)
    return rendered.replace("\r", " ").replace("\n", " ")


_FORM_TAG = re.compile(r"<form\b([^>]*)>", re.IGNORECASE)
_ACTION_ATTR = re.compile(r"""\saction\s*=\s*(?:"[^"]*"|'[^']*'|\S+)""", re.IGNORECASE)
_METHOD_ATTR = re.compile(r"\smethod\s*=", re.IGNORECASE)


def _point_forms_at(html: str, action_url: str) -> str:
    """Rewrite every <form> so it POSTs to our tracking endpoint. This makes any
    operator-authored login form capture the submission regardless of the action
    they wrote, without us having to trust that action."""

    def repl(m: re.Match[str]) -> str:
        attrs = _ACTION_ATTR.sub("", m.group(1))
        if not _METHOD_ATTR.search(attrs):
            attrs += ' method="post"'
        attrs += f' action="{escape(action_url, quote=True)}"'
        return f"<form{attrs}>"

    return _FORM_TAG.sub(repl, html)


def render_landing(body: str, ctx: RenderContext) -> str:
    """Render a landing page: personalize tokens (HTML-escaping recipient PII)
    and repoint forms at the submission endpoint. No tracking pixel is injected
    (the recipient already clicked to get here)."""
    out = _substitute(body, ctx, is_html=True)
    return _point_forms_at(out, tracker.landing_url(ctx.phish_url, ctx.rid))
