"""IMAP monitoring for user-reported phishing.

Employees report a simulated phish by forwarding it to a shared mailbox (e.g.
phish-report@company). This poller reads that mailbox, finds the campaign
recipient the reported message belongs to — by the tracking token embedded in
the forwarded email, or by the reporter's own address — and records a `reported`
event, crediting them (Security Champions).

Uses only the stdlib (imaplib/email). Blocking calls run in a worker thread via
the scheduler's asyncio.to_thread. Read-only intent: messages are marked \\Seen,
never deleted.
"""
from __future__ import annotations

import email
import imaplib
import logging
import re
from email.header import decode_header
from email.utils import parseaddr

from sqlalchemy import func, select

from ..database import SessionLocal
from ..models import EventType, Result
from .events import record_event

log = logging.getLogger("phishsim.imap")


class ImapError(RuntimeError):
    pass


# tracking tokens we embed in emails: /c/{rid} /t/{rid}.png /a/{rid}.png /q/{rid}.png /p/{rid} /r/{rid} /learn/{rid}
_RID_RE = re.compile(r"/(?:c|t|a|q|p|r|learn)/([A-Za-z0-9_\-]{6,})", re.IGNORECASE)
_SHORT_RE = re.compile(r"/s/([A-Za-z0-9]{4,})", re.IGNORECASE)


def get_imap_config(db) -> dict:  # noqa: ANN001
    from ..models import Setting
    from ..security import decrypt_secret

    def g(key: str, default: str = "") -> str:
        row = db.get(Setting, key)
        return row.value if row is not None and row.value not in (None, "") else default

    enc = db.get(Setting, "imap_password_enc")
    pw = decrypt_secret(enc.value) if (enc and enc.value) else ""
    try:
        port = int(g("imap_port", "993") or "993")
    except ValueError:
        port = 993
    return {
        "enabled": g("imap_enabled", "0") == "1",
        "host": g("imap_host"),
        "port": port,
        "username": g("imap_username"),
        "password": pw,
        "ssl": g("imap_ssl", "1") == "1",
        "folder": g("imap_folder", "INBOX") or "INBOX",
    }


def _connect(cfg: dict) -> imaplib.IMAP4:
    try:
        m = imaplib.IMAP4_SSL(cfg["host"], cfg["port"]) if cfg["ssl"] else imaplib.IMAP4(cfg["host"], cfg["port"])
        m.login(cfg["username"], cfg["password"])
        return m
    except (imaplib.IMAP4.error, OSError) as exc:
        raise ImapError(f"IMAP connection failed: {type(exc).__name__}")


def test_imap(cfg: dict) -> int:
    """Connect, login and count messages in the folder. Raises ImapError."""
    if not cfg["host"] or not cfg["username"]:
        raise ImapError("Host and username are required.")
    m = _connect(cfg)
    try:
        typ, data = m.select(cfg["folder"], readonly=True)
        if typ != "OK":
            raise ImapError(f"Folder '{cfg['folder']}' not found.")
        return int(data[0]) if data and data[0] else 0
    finally:
        try:
            m.logout()
        except Exception:  # noqa: BLE001
            pass


def _message_text(msg: email.message.Message) -> str:
    """Concatenate decoded text/plain + text/html bodies (handles QP/base64)."""
    parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode(part.get_content_charset() or "utf-8", "ignore"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            parts.append(payload.decode(msg.get_content_charset() or "utf-8", "ignore"))
    return "\n".join(parts)


def _match_result(db, msg, body: str) -> Result | None:  # noqa: ANN001
    # 1) tracking token in the forwarded body → exact recipient
    for rid in set(_RID_RE.findall(body)):
        r = db.query(Result).filter(Result.rid == rid).one_or_none()
        if r is not None:
            return r
    for code in set(_SHORT_RE.findall(body)):
        r = db.query(Result).filter(Result.short_code == code).one_or_none()
        if r is not None:
            return r
    # 2) fallback: the reporter's own address matches a recipient (they forwarded
    #    their own phish). Take their most recent result.
    _, addr = parseaddr(str(msg.get("From", "")))
    if addr and "@" in addr:
        r = (
            db.execute(
                select(Result).where(func.lower(Result.email) == addr.lower()).order_by(Result.id.desc())
            )
            .scalars()
            .first()
        )
        if r is not None:
            return r
    return None


def poll_reported() -> int:
    """Poll the configured mailbox; mark matched recipients as reported. Returns
    the number newly credited. Safe to call on every scheduler tick."""
    db = SessionLocal()
    try:
        cfg = get_imap_config(db)
        if not cfg["enabled"] or not cfg["host"] or not cfg["username"]:
            return 0
        try:
            m = _connect(cfg)
        except ImapError as exc:
            log.warning("IMAP poll: %s", exc)
            return 0
        marked = 0
        try:
            typ, _ = m.select(cfg["folder"])
            if typ != "OK":
                return 0
            typ, data = m.search(None, "UNSEEN")
            if typ != "OK" or not data or not data[0]:
                return 0
            for num in data[0].split():
                typ, msgdata = m.fetch(num, "(RFC822)")
                if typ != "OK" or not msgdata or not msgdata[0]:
                    continue
                try:
                    msg = email.message_from_bytes(msgdata[0][1])
                    body = _message_text(msg)
                    result = _match_result(db, msg, body)
                    if result is not None:
                        record_event(db, campaign_id=result.campaign_id, rid=result.rid, type=EventType.reported)
                        db.commit()
                        marked += 1
                except Exception:  # noqa: BLE001
                    log.exception("IMAP: failed to process a message")
                finally:
                    try:
                        m.store(num, "+FLAGS", "\\Seen")
                    except Exception:  # noqa: BLE001
                        pass
            return marked
        finally:
            try:
                m.logout()
            except Exception:  # noqa: BLE001
                pass
    finally:
        db.close()
