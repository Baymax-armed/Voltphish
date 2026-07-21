"""OpenID Connect (Authorization Code + PKCE) SSO for admin login.

Works with any compliant provider (Okta, Microsoft Entra ID, Google, Auth0,
Keycloak) via its discovery document. We validate the ID token signature against
the provider JWKS and check iss/aud/exp/nonce (authlib.jose — never hand-rolled).
Config lives in Settings; the client secret is AES-GCM encrypted at rest.

Single-node transient store for the in-flight (state -> nonce/verifier) handshake
with a short TTL. For multi-node, back this with Redis.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time

import httpx
from authlib.jose import JsonWebKey, jwt
from sqlalchemy.orm import Session as DbSession

from ..models import Setting
from ..models.base import utcnow
from ..security import decrypt_secret, encrypt_secret

log = logging.getLogger("voltphish.oidc")


class OidcError(RuntimeError):
    pass


# state -> (nonce, code_verifier, created_at)
_pending: dict[str, tuple[str, str, float]] = {}
_PENDING_TTL = 600  # 10 minutes

# issuer -> (discovery_doc, fetched_at)
_disco_cache: dict[str, tuple[dict, float]] = {}
_DISCO_TTL = 3600


def _g(db: DbSession, key: str, default: str = "") -> str:
    row = db.get(Setting, key)
    return row.value if row is not None and row.value not in (None, "") else default


def get_oidc_config(db: DbSession) -> dict:
    enc = db.get(Setting, "oidc_client_secret_enc")
    secret = decrypt_secret(enc.value) if (enc and enc.value) else ""
    domains = [d.strip().lower() for d in _g(db, "oidc_allowed_domains").split(",") if d.strip()]
    return {
        "enabled": _g(db, "oidc_enabled", "0") == "1",
        "issuer": _g(db, "oidc_issuer").rstrip("/"),
        "client_id": _g(db, "oidc_client_id"),
        "client_secret": secret,
        "allowed_domains": domains,
        "auto_provision": _g(db, "oidc_auto_provision", "0") == "1",
        "button_label": _g(db, "oidc_button_label", "Sign in with SSO") or "Sign in with SSO",
    }


def set_oidc_config(
    db: DbSession, *, enabled: bool, issuer: str, client_id: str,
    client_secret: str | None, allowed_domains: str, auto_provision: bool, button_label: str,
) -> None:
    def s(key: str, value: str | None) -> None:
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value, modified_at=utcnow()))
        else:
            row.value = value
            row.modified_at = utcnow()

    s("oidc_enabled", "1" if enabled else "0")
    s("oidc_issuer", issuer.rstrip("/"))
    s("oidc_client_id", client_id)
    if client_secret:  # None/"" => keep existing
        s("oidc_client_secret_enc", encrypt_secret(client_secret))
    s("oidc_allowed_domains", allowed_domains)
    s("oidc_auto_provision", "1" if auto_provision else "0")
    s("oidc_button_label", button_label or "Sign in with SSO")
    db.commit()


def _discovery(issuer: str) -> dict:
    now = time.time()
    cached = _disco_cache.get(issuer)
    if cached and now - cached[1] < _DISCO_TTL:
        return cached[0]
    url = f"{issuer}/.well-known/openid-configuration"
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            raise OidcError("Could not load provider configuration")
        doc = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcError("Could not reach the identity provider") from exc
    _disco_cache[issuer] = (doc, now)
    return doc


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _sweep() -> None:
    now = time.time()
    for k in [k for k, v in _pending.items() if now - v[2] > _PENDING_TTL]:
        _pending.pop(k, None)


def begin_login(db: DbSession, redirect_uri: str) -> str:
    """Return the provider authorize URL; stash state/nonce/verifier."""
    cfg = get_oidc_config(db)
    if not cfg["enabled"] or not cfg["issuer"] or not cfg["client_id"]:
        raise OidcError("SSO is not configured")
    disco = _discovery(cfg["issuer"])
    authz = disco.get("authorization_endpoint")
    if not authz:
        raise OidcError("Provider has no authorization endpoint")

    _sweep()
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    _pending[state] = (nonce, verifier, time.time())

    from urllib.parse import urlencode

    params = {
        "client_id": cfg["client_id"],
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": redirect_uri,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{authz}?{urlencode(params)}"


def complete_login(db: DbSession, *, code: str, state: str, redirect_uri: str) -> dict:
    """Exchange the code, validate the ID token, return verified claims (email…)."""
    entry = _pending.pop(state, None)
    if entry is None:
        raise OidcError("Invalid or expired sign-in state")
    nonce, verifier, _ = entry

    cfg = get_oidc_config(db)
    disco = _discovery(cfg["issuer"])
    token_endpoint = disco.get("token_endpoint")
    jwks_uri = disco.get("jwks_uri")
    if not token_endpoint or not jwks_uri:
        raise OidcError("Provider is missing token/JWKS endpoints")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": cfg["client_id"],
        "code_verifier": verifier,
    }
    if cfg["client_secret"]:
        data["client_secret"] = cfg["client_secret"]

    try:
        with httpx.Client(timeout=10.0) as client:
            tok = client.post(token_endpoint, data=data, headers={"Accept": "application/json"})
            if tok.status_code != 200:
                raise OidcError("Token exchange failed")
            token = tok.json()
            id_token = token.get("id_token")
            if not id_token:
                raise OidcError("No ID token returned")
            jwks_resp = client.get(jwks_uri)
            jwks_resp.raise_for_status()
            jwks = jwks_resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcError("Could not complete sign-in with the provider") from exc

    try:
        key_set = JsonWebKey.import_key_set(jwks)
        claims = jwt.decode(
            id_token, key_set,
            claims_options={
                "iss": {"essential": True, "value": cfg["issuer"]},
                "aud": {"essential": True, "value": cfg["client_id"]},
                "exp": {"essential": True},
            },
        )
        claims.validate(leeway=60)
    except Exception as exc:  # noqa: BLE001 — authlib raises various JOSE errors
        log.warning("OIDC token validation failed: %s", type(exc).__name__)
        raise OidcError("Sign-in verification failed")

    if claims.get("nonce") != nonce:
        raise OidcError("Sign-in nonce mismatch")

    email = (claims.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise OidcError("No email in the SSO profile")
    if claims.get("email_verified") is False:
        raise OidcError("Your SSO email is not verified")
    if cfg["allowed_domains"]:
        domain = email.rsplit("@", 1)[-1]
        if domain not in cfg["allowed_domains"]:
            raise OidcError("Your email domain is not allowed to sign in")

    return {"email": email, "name": claims.get("name") or "", "auto_provision": cfg["auto_provision"]}
