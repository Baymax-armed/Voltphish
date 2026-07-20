"""QR-code generation for quishing (QR-phishing) simulations.

A quishing email embeds a QR code that, when scanned with a phone camera, opens
the per-recipient click-tracking URL — exactly like a malicious "scan to verify"
lure. We serve the QR as a normal server-hosted PNG (data: URIs are stripped by
most mail clients) so it renders in Outlook/Gmail and can even double as a
weak open-signal when the image loads.

Pure-Python (segno) — no PIL, no native deps.
"""
from __future__ import annotations

import io

import segno


def qr_png(text: str, *, scale: int = 6, border: int = 2) -> bytes:
    """Render `text` as a PNG QR code and return the raw bytes.

    error='m' (~15% recovery) keeps the code scannable even if slightly
    obscured by an email client's rendering, without bloating the module count.
    """
    qr = segno.make(text, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, border=border)
    return buf.getvalue()
