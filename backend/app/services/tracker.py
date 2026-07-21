"""Builders for the per-recipient tracking URLs embedded in simulation emails.

The phishing/tracking server (app/phish/server.py) serves these paths:
  GET  /t/{rid}.png   -> 1x1 pixel, records "email_opened"
  GET  /c/{rid}       -> records "clicked_link", then redirects
  GET  /p/{rid}       -> landing page (later phase)
  POST /p/{rid}       -> records "submitted_data" (password never stored)
  GET  /r/{rid}       -> records "reported"
"""
from __future__ import annotations

from urllib.parse import urljoin


def _base(phish_url: str) -> str:
    return phish_url if phish_url.endswith("/") else phish_url + "/"


def open_pixel_url(phish_url: str, rid: str) -> str:
    return urljoin(_base(phish_url), f"t/{rid}.png")


def click_url(phish_url: str, rid: str) -> str:
    return urljoin(_base(phish_url), f"c/{rid}")


def short_click_url(phish_url: str, code: str) -> str:
    """Short click-tracking URL for SMS (e.g. https://host/s/ab2cd3e)."""
    return urljoin(_base(phish_url), f"s/{code}")


def landing_url(phish_url: str, rid: str) -> str:
    return urljoin(_base(phish_url), f"p/{rid}")


def attach_pixel_url(phish_url: str, rid: str) -> str:
    """Tracking-pixel URL to embed in a lure attachment (records attachment_opened)."""
    return urljoin(_base(phish_url), f"a/{rid}.png")


def qr_url(phish_url: str, rid: str) -> str:
    """URL of the per-recipient QR-code PNG (encodes this recipient's click
    link). Scanning it opens /c/{rid} and records the click (quishing)."""
    return urljoin(_base(phish_url), f"q/{rid}.png")


def report_url(phish_url: str, rid: str) -> str:
    return urljoin(_base(phish_url), f"r/{rid}")
