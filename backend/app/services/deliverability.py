"""Deliverability pre-flight: check a sending domain's SPF / DKIM / DMARC DNS.

A campaign whose From-domain lacks SPF/DMARC (or whose sending server isn't in
the SPF record) tends to land in spam or fail authentication — exactly the class
of problem that made earlier real sends fail. This gives operators a quick,
read-only DNS check before they launch.

Read-only DNS TXT lookups only; no HTTP, so no SSRF surface. Bounded timeouts.
"""
from __future__ import annotations

import re

import dns.exception
import dns.resolver

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,63}$")
_TIMEOUT = 5.0


class DeliverabilityError(ValueError):
    pass


def _resolver() -> dns.resolver.Resolver:
    # Query public resolvers directly. In containers the default embedded DNS
    # (127.0.0.11) can time out on larger TXT record sets / TCP fallback, so we
    # use Cloudflare + Google, which handle these reliably.
    r = dns.resolver.Resolver(configure=False)
    r.nameservers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
    r.timeout = 4.0
    r.lifetime = _TIMEOUT
    return r


def _txt(name: str) -> list[str]:
    try:
        answers = _resolver().resolve(name, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except dns.exception.DNSException:
        return []
    out: list[str] = []
    for rec in answers:
        try:
            out.append(b"".join(rec.strings).decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            continue
    return out


def _first(records: list[str], marker: str) -> str | None:
    marker = marker.lower()
    for r in records:
        if r.lower().startswith(marker) or marker in r.lower():
            return r
    return None


def check_domain(domain: str, selector: str | None = None) -> dict:
    domain = (domain or "").strip().lower().rstrip(".")
    if not _DOMAIN_RE.match(domain):
        raise DeliverabilityError("Enter a valid domain, e.g. example.com")

    # SPF — TXT at the domain apex.
    spf_txts = _txt(domain)
    spf = _first(spf_txts, "v=spf1")

    # DMARC — TXT at _dmarc.<domain>.
    dmarc = _first(_txt(f"_dmarc.{domain}"), "v=dmarc1")

    # DKIM — only checkable with a selector (selector._domainkey.<domain>).
    dkim = None
    dkim_checked = bool(selector)
    if selector:
        selector = selector.strip().lower()
        dkim = _first(_txt(f"{selector}._domainkey.{domain}"), "v=dkim1") or _first(
            _txt(f"{selector}._domainkey.{domain}"), "p="
        )

    checks = [
        {
            "key": "spf",
            "label": "SPF",
            "status": "pass" if spf else "fail",
            "record": spf,
            "note": (
                "SPF record found. Make sure your sending server's IP is authorized in it."
                if spf
                else "No SPF record — receivers can't verify who may send for this domain. Mail often lands in spam."
            ),
        },
        {
            "key": "dmarc",
            "label": "DMARC",
            "status": "pass" if dmarc else "warn",
            "record": dmarc,
            "note": (
                "DMARC policy found."
                if dmarc
                else "No DMARC record. Add one (start with p=none) to monitor authentication."
            ),
        },
        {
            "key": "dkim",
            "label": "DKIM",
            "status": ("pass" if dkim else "fail") if dkim_checked else "skip",
            "record": dkim,
            "note": (
                ("DKIM key found for this selector." if dkim else "No DKIM key at that selector — check the selector name.")
                if dkim_checked
                else "Enter your DKIM selector (e.g. 'default', 's1') to check DKIM."
            ),
        },
    ]

    passed = sum(1 for c in checks if c["status"] == "pass")
    if spf and dmarc:
        verdict = "good"
        summary = "Core authentication (SPF + DMARC) is in place."
    elif spf or dmarc:
        verdict = "partial"
        summary = "Partial setup — add the missing records to improve inboxing."
    else:
        verdict = "poor"
        summary = "No SPF or DMARC — simulations will likely be filtered as spam."

    return {"domain": domain, "verdict": verdict, "summary": summary, "passed": passed, "checks": checks}
