"""Import a landing page by fetching a URL (Gophish "Import Site").

The URL is user-supplied, so every hop goes through the SSRF guard
(services/ssrf.py) before any request — no internal/metadata targets. Redirects
are followed manually (max 3) so each hop is re-validated; the response size is
capped. A <base> tag is injected so the imported page's relative assets resolve
against the original site."""
from __future__ import annotations

from html import escape
from urllib.parse import urljoin

import httpx

from .ssrf import validate_url

_MAX_BYTES = 3_000_000
_TIMEOUT = 10.0
_MAX_REDIRECTS = 3
_UA = "Mozilla/5.0 (compatible; PhishSim-SiteImport/1.0)"


class SiteImportError(ValueError):
    pass


def _inject_base(html: str, page_url: str) -> str:
    tag = f'<base href="{escape(page_url, quote=True)}">'
    low = html.lower()
    idx = low.find("<head")
    if idx != -1:
        end = low.find(">", idx)
        if end != -1:
            return html[: end + 1] + tag + html[end + 1 :]
    return tag + html


def fetch_site(url: str) -> dict[str, str]:
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        validate_url(current)  # SSRF check on every hop
        try:
            with httpx.Client(
                follow_redirects=False, timeout=_TIMEOUT, headers={"User-Agent": _UA}
            ) as client:
                resp = client.get(current)
        except httpx.HTTPError as exc:
            raise SiteImportError(f"could not fetch the URL: {type(exc).__name__}") from exc

        if resp.is_redirect:
            location = resp.headers.get("location")
            if not location:
                raise SiteImportError("redirect without a location")
            current = urljoin(current, location)
            continue

        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype.lower():
            raise SiteImportError(f"URL did not return HTML (got '{ctype or 'unknown'}')")

        html = resp.text
        if len(html.encode("utf-8", "ignore")) > _MAX_BYTES:
            raise SiteImportError("page is too large to import")
        return {"html": _inject_base(html, current), "url": current}

    raise SiteImportError("too many redirects")
