# SECURITY.md — VoltPhish

## Purpose & authorized use

VoltPhish runs **consented** phishing simulations for security-awareness training.
It is not a tool for compromising third parties. The trust model assumes:

- Operators are authenticated staff running tests **within an authorized scope**.
- Recipients are people the operating organization is permitted to test.

## Trust boundaries

| Boundary | Notes |
|---|---|
| Admin API (`/api/v1/*`) | Authenticated + role-gated. Never trust client-supplied IDs over the session. |
| Public tracking server (`/t`,`/c`,`/p`,`/r`) | Unauthenticated by design. Hit by arbitrary internet clients. Must be safe against invalid/forged `rid`s and must never leak whether an `rid` is valid. |
| Database | Holds recipient PII and encrypted SMTP secrets. Admin passwords are hashed (argon2id). Submitted form values are not stored by default; full capture (incl. passwords) is an explicit opt-in for authorized engagements. |
| SMTP egress | Outbound only, TLS-verified by default. |

## STRIDE (abbreviated)

- **Spoofing:** session cookies are HttpOnly/Secure/SameSite; tokens are 256-bit
  CSPRNG and stored hashed; login is rate-limited with lockout and gives generic
  errors (no user enumeration).
- **Tampering:** audit events are append-only; all writes go through Pydantic
  validation and parameterized ORM queries.
- **Repudiation:** every campaign action is logged with actor/IP/timestamp.
- **Information disclosure:** submitted form values are not stored by default
  (full capture is an explicit, warned opt-in); SMTP passwords
  are AES-256-GCM encrypted at rest and never returned; errors are generic to
  clients with detail only in server logs.
- **DoS:** login rate limiting; bounded SMTP concurrency; per-call timeouts.
  (Gateway-level rate limiting is expected in front of this in production.)
- **Elevation of privilege:** default-deny auth on every admin route; `admin`
  role required for privileged actions.

## Control mapping (CLAUDE.md / OWASP Top 10 2021)

| Control | Where |
|---|---|
| A01 Access control — default-deny, server-side authz | `dependencies.py`, router `dependencies=[Depends(...)]` |
| A02 Crypto — argon2id, AES-256-GCM, CSPRNG tokens | `security.py` |
| A03 Injection — ORM only, safe token substitution (no SSTI), header-injection strip, landing-page PII HTML-escaped | `renderer.py`, all routers |
| Ethical guardrail — landing-page forms repointed to our tracker; submitted values not stored by default, full capture an explicit opt-in | `renderer.py`, `phish/server.py`, `config.py` |
| A04 Insecure design — login lockout/backoff | `services/ratelimit.py`, `routers/auth.py` |
| A05 Misconfig — security headers, prod fail-closed, docs off in prod | `middleware.py`, `config.py` |
| A07 Auth failures — session rotation, server-side invalidation, no enumeration | `routers/auth.py` |
| CSRF — per-session double-submit token required on state-changing requests | `csrf.py`, `routers/auth.py` |
| A09 Logging — append-only events, secrets never logged | `models/event.py`, `services/events.py` |
| A10 SSRF | Webhook delivery gated by an allow/deny resolver (blocks private/link-local/metadata); redirects disabled | `services/ssrf.py`, `services/handlers.py` |

## Known gaps / roadmap (tracked, not yet done)

- **Rate limiting** is in-process (single node). Use Redis / a gateway for
  multi-node production.
- **Background sends & webhook delivery** run on a durable, DB-backed job queue
  (`jobs` table) with atomic claiming, retries, and orphan-requeue on restart —
  so work survives restarts. True parallel multi-worker requires Postgres
  (SQLite serializes writers); jobs are still durable on SQLite.
- **Migrations:** managed by Alembic, auto-applied on startup, with adoption
  logic (stamp/upgrade) for pre-existing databases.
- **CORS** is not enabled (same-origin only). Configure an explicit allowlist
  when the SPA is served from a different origin.

## Outbound requests (webhooks) — SSRF (A10)

Webhook target URLs are user-supplied, so every delivery is gated by
`services/ssrf.py`: only http/https, and the resolved address must not be
loopback, private (RFC1918), link-local, unique-local, reserved, multicast, or a
cloud-metadata endpoint (`169.254.169.254`, `metadata.google.internal`, …).
Redirects are disabled so a 3xx can't bounce delivery to an internal host.
Deliveries are HMAC-SHA256 signed (`X-VoltPhish-Signature`) with the per-webhook
secret (encrypted at rest). Residual risk: DNS rebinding between the resolve-time
check and connect — route egress through an enforcing proxy for high assurance.

## REST API keys (A02/A07)

Keys are high-entropy (`psk_` + 256 bits), stored only as a SHA-256 hash, shown
once at creation. Bearer auth is CSRF-exempt by design (the credential is not a
cookie the browser auto-sends). Keys are owner-scoped and individually revocable;
disabling a user's account also stops their keys (auth checks `is_active`).

## Reporting

Found an issue? Do not open a public issue with exploit detail. Contact the
maintainers privately.
