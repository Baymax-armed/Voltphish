"""Cloudflare Tunnel discovery.

When a `cloudflared` sidecar runs a quick tunnel (`tunnel --url http://voltphish:8080`),
it assigns a random public https://…trycloudflare.com hostname and exposes it on
its metrics server at GET /quicktunnel -> {"hostname": "..."}. We read that so the
app can offer / use the live public URL for recipient-facing links (campaign
tracking AND training-invite emails) without any manual copy-paste.

The result is cached briefly so callers don't hammer cloudflared, but short
enough that a tunnel restart (new hostname) is picked up quickly.

All functions are sync and never raise — link building must not break if the
tunnel is down or misconfigured."""
from __future__ import annotations

import logging
import time

import httpx

from ..config import get_settings

log = logging.getLogger("voltphish.tunnel")

_CACHE_TTL = 15.0  # seconds
_cache: tuple[float, str | None] = (0.0, None)


def detect_public_url(*, force: bool = False) -> str | None:
    """Return the tunnel's public https URL, or None if no tunnel is configured
    or reachable."""
    global _cache
    metrics = get_settings().tunnel_metrics_url.strip()
    if not metrics:
        return None

    now = time.monotonic()
    if not force and now - _cache[0] < _CACHE_TTL:
        return _cache[1]

    url: str | None = None
    try:
        resp = httpx.get(metrics.rstrip("/") + "/quicktunnel", timeout=3.0)
        if resp.status_code == 200:
            host = (resp.json() or {}).get("hostname", "").strip()
            if host:
                url = host if host.startswith("http") else f"https://{host}"
    except Exception as exc:  # noqa: BLE001 — detection must never break the UI/links
        log.debug("tunnel detect failed: %s", exc)
        url = None

    _cache = (now, url)
    return url


def resolve_public_base_url() -> str:
    """Best base URL for links recipients must actually reach: the live tunnel
    if one is up, otherwise the configured phish_base_url."""
    return detect_public_url() or get_settings().phish_base_url


def is_configured() -> bool:
    return bool(get_settings().tunnel_metrics_url.strip())
