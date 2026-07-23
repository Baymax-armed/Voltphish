# ⚡ VoltPhish

**Free, open-source, self-hosted phishing simulation & security-awareness training platform.**

Run the whole awareness program from one container: send an email or QR phishing lure, track who clicks, train them the moment they slip, catch the employees who report it, and measure human risk over time. A self-hostable alternative to commercial tools like KnowBe4 and Proofpoint, and a full-program upgrade over email-only tools like GoPhish.

- **Source & docs:** https://github.com/Baymax-armed/Voltphish
- **License:** MIT

## Quick start

```bash
docker run -d --name voltphish \
  -p 8010:8080 \
  -e VOLTPHISH_SECRET_KEY="$(openssl rand -base64 48)" \
  -v voltphish-data:/data \
  <your-dockerhub-username>/voltphish:latest
```

Then open **http://localhost:8010** and grab the first-run admin password from the logs:

```bash
docker logs voltphish | grep -A3 "first-run"
```

Prefer Compose (with the Cloudflare tunnel option and full config)? Use the [`docker-compose.yml`](https://github.com/Baymax-armed/Voltphish/blob/main/docker-compose.yml) from the repo.

## Tags

- `latest` — most recent release
- `x.y.z` — pinned version

Images are published for **linux/amd64** and **linux/arm64** (works on Intel/AMD servers and Apple Silicon / Raspberry Pi).

## What's inside

Email + QR (quishing) + calendar lures · AI-assisted lure generation · report-phish button (Outlook/Gmail) · training LMS with adaptive auto-enroll · human-risk scoring · geo map · SSO (OIDC) · admin 2FA · RBAC · deliverability toolkit · signed webhooks + REST API. Secure by default (argon2id, AES-256-GCM, CSRF/SSRF protection, security headers). Submitted passwords are never stored.

## Configuration (common env vars)

| Variable | Purpose |
|---|---|
| `VOLTPHISH_SECRET_KEY` | **Required in production.** 48+ random chars; app refuses to start without it. |
| `VOLTPHISH_BOOTSTRAP_ADMIN_PASSWORD` | Set your own first-run admin password (else one is generated and logged). |
| `VOLTPHISH_MAIL_BACKEND` | `smtp` (default — sends real email via the profile) or `console` (dry-run: writes `.eml` files, no real email). |
| `VOLTPHISH_COOKIE_SECURE` | Set `true` when serving over HTTPS. |

Data (SQLite + outbox) persists in the volume mounted at `/data`.

> ⚠️ **Authorized use only.** VoltPhish is for testing people who have agreed to be tested — your own organization, a scoped client engagement, or a lab you own. Using it against anyone else is likely illegal.
