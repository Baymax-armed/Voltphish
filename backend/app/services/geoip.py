"""Best-effort geolocation of recorded click IPs for the results map.

Uses the free ip-api.com batch endpoint (no key, 100 IPs/request) with a simple
in-memory cache so we don't re-query the same IP. Private/loopback/dev IPs are
bucketed as "Local/Private" without any outbound call. Failures degrade to
"Unknown" — geolocation is a nice-to-have, never load-bearing.
"""
from __future__ import annotations

import ipaddress
import logging

import httpx

log = logging.getLogger("voltphish.geoip")

_cache: dict[str, dict] = {}


def _is_public(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (a.is_private or a.is_loopback or a.is_reserved or a.is_link_local or a.is_multicast or a.is_unspecified)


async def geolocate(ips: list[str]) -> dict[str, dict]:
    """Return {ip: {"country": str, "code": str(2-letter, lowercase)}}."""
    out: dict[str, dict] = {}
    todo: list[str] = []
    for ip in {i for i in ips if i}:
        if ip in _cache:
            out[ip] = _cache[ip]
        elif not _is_public(ip):
            _cache[ip] = {"country": "Local/Private", "code": ""}
            out[ip] = _cache[ip]
        else:
            todo.append(ip)

    for i in range(0, len(todo), 100):
        chunk = todo[i : i + 100]
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    "http://ip-api.com/batch?fields=status,country,countryCode,query", json=chunk
                )
            rows = resp.json() if resp.status_code == 200 else []
        except (httpx.HTTPError, ValueError):
            rows = []
        seen = set()
        for row in rows:
            ip = row.get("query")
            if not ip:
                continue
            if row.get("status") == "success":
                g = {"country": row.get("country") or "Unknown", "code": (row.get("countryCode") or "").lower()}
            else:
                g = {"country": "Unknown", "code": ""}
            _cache[ip] = g
            out[ip] = g
            seen.add(ip)
        for ip in chunk:
            if ip not in seen:
                out.setdefault(ip, {"country": "Unknown", "code": ""})
    return out
