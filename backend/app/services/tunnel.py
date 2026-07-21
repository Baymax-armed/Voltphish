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
import os
import shutil
import socket
import subprocess
import threading
import time

import httpx

from ..config import get_settings

log = logging.getLogger("voltphish.tunnel")

_CACHE_TTL = 15.0  # seconds
_cache: tuple[float, str | None] = (0.0, None)
_detect_lock = threading.Lock()
_detecting = False

# ── App-managed per-campaign quick tunnels ──────────────────────────────────
# When the cloudflared binary is bundled, the app can spawn a dedicated quick
# tunnel per campaign so every new/cloned campaign gets its OWN public URL (a
# separate process = a separate …trycloudflare.com hostname, all valid at once).
# Bounded so a runaway can't spawn unlimited processes; tunnels are in-memory
# and do NOT survive an app restart (an inherent quick-tunnel limitation).
_MAX_TUNNELS = 8
_APP_ORIGIN = "http://127.0.0.1:8080"
_mlock = threading.Lock()
_tunnels: dict[int, dict] = {}  # campaign_id -> {"proc", "url", "port"}


def _cloudflared_bin() -> str | None:
    return shutil.which("cloudflared") or (
        "/usr/local/bin/cloudflared" if os.path.exists("/usr/local/bin/cloudflared") else None
    )


def managed_available() -> bool:
    """True when the app can spawn its own per-campaign tunnels."""
    return _cloudflared_bin() is not None


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _read_hostname(port: int, timeout: float = 25.0) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/quicktunnel", timeout=2.0)
            if r.status_code == 200:
                host = (r.json() or {}).get("hostname", "").strip()
                if host:
                    return host
        except Exception:  # noqa: BLE001 — cloudflared not ready yet
            pass
        time.sleep(0.7)
    return None


def _stop_locked(campaign_id: int) -> None:
    t = _tunnels.pop(campaign_id, None)
    if t:
        try:
            t["proc"].terminate()
        except Exception:  # noqa: BLE001
            pass


def spawn_campaign_tunnel(campaign_id: int) -> str | None:
    """Start a dedicated quick tunnel for a campaign and return its public URL,
    or None if unavailable/failed. Reuses an existing one for the campaign."""
    binpath = _cloudflared_bin()
    if not binpath:
        return None
    with _mlock:
        existing = _tunnels.get(campaign_id)
        if existing:
            return existing["url"]
        if len(_tunnels) >= _MAX_TUNNELS:
            _stop_locked(next(iter(_tunnels)))  # reap oldest
        port = _free_port()
        try:
            proc = subprocess.Popen(
                [binpath, "tunnel", "--no-autoupdate", "--url", _APP_ORIGIN, "--metrics", f"127.0.0.1:{port}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:  # noqa: BLE001
            log.exception("failed to spawn cloudflared")
            return None

    host = _read_hostname(port)  # slow — done outside the lock
    if not host:
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass
        log.warning("cloudflared did not report a hostname for campaign %s", campaign_id)
        return None

    url = f"https://{host}"
    with _mlock:
        _tunnels[campaign_id] = {"proc": proc, "url": url, "port": port}
    log.info("spawned per-campaign tunnel for %s: %s", campaign_id, url)
    return url


def stop_campaign_tunnel(campaign_id: int) -> None:
    with _mlock:
        _stop_locked(campaign_id)


def _refresh_shared_detect() -> None:
    global _cache, _detecting
    metrics = get_settings().tunnel_metrics_url.strip()
    url: str | None = None
    if metrics:
        try:
            resp = httpx.get(metrics.rstrip("/") + "/quicktunnel", timeout=httpx.Timeout(2.5, connect=2.5))
            if resp.status_code == 200:
                host = (resp.json() or {}).get("hostname", "").strip()
                if host:
                    url = host if host.startswith("http") else f"https://{host}"
        except Exception as exc:  # noqa: BLE001 — sidecar down / host unresolvable
            log.debug("tunnel detect failed: %s", exc)
    with _detect_lock:
        _cache = (time.monotonic(), url)
        _detecting = False


def detect_public_url(*, force: bool = False) -> str | None:
    """Return the shared sidecar tunnel's public URL, or None. NON-BLOCKING:
    returns the cached value immediately and refreshes it in a background thread,
    so a hung/unresolvable sidecar host can never stall the caller (e.g. the
    campaign form, which mainly needs `managed`). A live sidecar shows up on the
    next poll a second or two later."""
    global _detecting
    if not get_settings().tunnel_metrics_url.strip():
        return None
    now = time.monotonic()
    with _detect_lock:
        stale = now - _cache[0] >= _CACHE_TTL
        cached = _cache[1]
        if (stale or force) and not _detecting:
            _detecting = True
            threading.Thread(target=_refresh_shared_detect, daemon=True).start()
    return cached


def resolve_public_base_url() -> str:
    """Best base URL for links recipients must actually reach: the live tunnel
    if one is up, otherwise the configured phish_base_url."""
    return detect_public_url() or get_settings().phish_base_url


def is_configured() -> bool:
    return bool(get_settings().tunnel_metrics_url.strip())
