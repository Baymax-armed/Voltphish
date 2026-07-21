"""SSRF guard for outbound HTTP to user-supplied URLs (CLAUDE.md A10).

Before we POST to a webhook target, we resolve its hostname and reject the
request if any resolved address is loopback, private (RFC1918), link-local,
unique-local, reserved, multicast, or a known cloud metadata endpoint. Only http
and https on standard-ish ports are allowed, and redirects are disabled by the
caller so a 3xx can't bounce us to an internal host.

Caveat: this validates at resolve time; a determined attacker could DNS-rebind
between check and connect. For high-assurance deployments, route egress through a
proxy that enforces these rules at connect time (noted in SECURITY.md)."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

_BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata",
}
# Cloud metadata IPs (AWS/GCP/Azure/OpenStack, and IPv6 variants).
_BLOCKED_IPS = {"169.254.169.254", "fd00:ec2::254"}

_ALLOWED_SCHEMES = {"http", "https"}


class SsrfError(ValueError):
    pass


def _ip_is_blocked(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    # Unwrap IPv4-mapped/compatible IPv6 (e.g. ::ffff:169.254.169.254) so the
    # classification below sees the real IPv4 address instead of letting it pass.
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        addr = mapped
    if ip in _BLOCKED_IPS or str(addr) in _BLOCKED_IPS:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or (isinstance(addr, ipaddress.IPv6Address) and addr.is_site_local)
    )


def validate_url(url: str) -> None:
    """Raise SsrfError if the URL is not safe to fetch."""
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise SsrfError(f"scheme '{parts.scheme}' not allowed")
    host = parts.hostname
    if not host:
        raise SsrfError("missing host")
    if host.lower() in _BLOCKED_HOSTS:
        raise SsrfError("host is blocked")

    # Resolve all addresses and ensure none are internal.
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise SsrfError(f"DNS resolution failed: {exc}") from exc

    for info in infos:
        ip = info[4][0]
        if _ip_is_blocked(ip):
            raise SsrfError(f"resolves to a blocked address ({ip})")
