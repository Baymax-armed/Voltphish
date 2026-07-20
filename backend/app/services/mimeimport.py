"""Parse a raw MIME email (.eml) into subject/html/text for a template.

Uses the stdlib email parser (no code execution risk; input size is capped by
the request schema). Attachments are ignored."""
from __future__ import annotations

from email import message_from_string
from email.message import Message
from email.utils import parseaddr


def _decode(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


def parse_email(raw: str) -> dict[str, str | None]:
    msg = message_from_string(raw)

    subject = str(msg.get("Subject", "") or "").replace("\r", " ").replace("\n", " ").strip()
    _, sender = parseaddr(msg.get("From", "") or "")

    html: str | None = None
    text: str | None = None
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        disp = str(part.get("Content-Disposition", "") or "")
        if "attachment" in disp.lower():
            continue
        ctype = part.get_content_type()
        if ctype == "text/html" and html is None:
            html = _decode(part)
        elif ctype == "text/plain" and text is None:
            text = _decode(part)

    return {
        "subject": subject or "(no subject)",
        "envelope_sender": sender or None,
        "html": html,
        "text": text,
    }
