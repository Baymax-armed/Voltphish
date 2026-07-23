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


def qr_html_table(text: str, *, module_px: int = 5, border: int = 3) -> str:
    """Render `text` as a QR code built entirely from HTML table cells (no image).

    Outlook (and others) block images from external/unverified senders, so an
    <img> QR shows as a broken placeholder — the recipient sees nothing to scan.
    A table of coloured <td> cells always renders, because cell background
    colours are not gated behind "download images". It stays scannable and
    encodes the same URL, so a phone camera opens the tracked link exactly like
    the PNG would. `border` adds the white quiet-zone modules a scanner needs.

    error='l' (~7% recovery) keeps the module count — and thus the HTML size —
    small; a table QR renders pixel-perfect, so it needs no extra recovery margin.
    """
    qr = segno.make(text, error="l")

    def _cell(bit: int, span: int) -> str:
        # Merge runs of same-colour modules into one colspan cell (run-length
        # encoding) so the HTML stays small — a full per-module table is ~200 KB
        # and Gmail clips messages over ~102 KB.
        w = span * module_px
        bg = ' bgcolor="#000000"' if bit else ""
        return (
            f'<td colspan="{span}" width="{w}" height="{module_px}"{bg} '
            f'style="line-height:0;font-size:0;padding:0;border:0"></td>'
        )

    rows: list[str] = []
    for row in qr.matrix_iter(scale=1, border=border):
        cells: list[str] = []
        run = list(row)
        i, n = 0, len(run)
        while i < n:
            j = i
            while j < n and run[j] == run[i]:
                j += 1
            cells.append(_cell(run[i], j - i))
            i = j
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'bgcolor="#ffffff" style="border-collapse:collapse;background:#fff;'
        'mso-table-lspace:0;mso-table-rspace:0;display:inline-block" '
        'aria-label="Scan the QR code to continue">'
        + "".join(rows)
        + "</table>"
    )
