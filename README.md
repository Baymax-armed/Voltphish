<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/logo-light.png" />
    <img src="frontend/public/logo.png" alt="VoltPhish" width="300" />
  </picture>

  <h1>VoltPhish</h1>
  <p><strong>The modern, open-source phishing-simulation & human-risk platform.</strong><br/>
  Run realistic attack simulations, turn every fail into a lesson, and measure your people's risk — all from one Docker container.</p>

  <p>
    <img alt="License" src="https://img.shields.io/badge/license-MIT-blue" />
    <img alt="Backend" src="https://img.shields.io/badge/backend-FastAPI-009688" />
    <img alt="Frontend" src="https://img.shields.io/badge/frontend-React%2018%20%2B%20TS-61dafb" />
    <img alt="Deploy" src="https://img.shields.io/badge/deploy-Docker%20(1%20command)-2496ed" />
  </p>
</div>

> ⚠️ **Authorized use only.** VoltPhish is for testing organizations and people who have **consented** to being tested — your own company, a client engagement with signed scope, or a lab. Using it against anyone else is likely illegal. See [Responsible use](#-responsible-use).

---

## Why VoltPhish

Most phishing tools stop at "who clicked." VoltPhish closes the loop: **attack → teach → measure.** It's a full-stack app (React admin + FastAPI backend + tracking server) that runs as **one process in one container**, secure-by-default, with a UI built for people who run awareness programs — not just red teams.

## ✨ Highlights

### Attack simulations
- **📧 Email phishing** — WYSIWYG templates with `{{.FirstName}}` / `{{.URL}}` personalization, a ready-made **gallery** (IT, Microsoft 365, Google, HR, courier, MFA…), `.eml` import, and attachments.
- **🎣 Quishing (QR-code phishing)** — per-recipient QR codes that open the tracking link; served server-side so they render in Outlook/Gmail.
- **🖱️ ClickFix "verify you're human"** — the 2025 fake-CAPTCHA lure, as a safe landing page.
- **🪟 Browser-in-the-Browser** — a fake SSO popup with a spoofed address bar.
- **🤖 AI template generator** — describe a scenario, get a drafted email (bring your own LLM key).
- **🖥️ Landing pages** — a gallery of login clones + form pages; any `<form>` is auto-captured (passwords **never** stored).

### Close the loop & measure
- **🎓 Just-in-time training** — anyone who clicks/submits lands on a teaching page with the red flags + a tracked "I understand."
- **🧠 Human Risk Score** — a behaviour-based risk index per user and per department.
- **🏆 Security Champions** — a leaderboard of the people who *report* the phish.
- **📊 Dashboard** — engagement funnel, timeline chart, at-risk users, campaign breakdowns.
- **📄 Board report** — one-click printable/PDF executive summary.

### Ops & delivery
- **🔔 Real-time Slack / Microsoft Teams alerts** the moment someone clicks or submits.
- **📬 Deliverability pre-flight** — check a domain's SPF / DKIM / DMARC before you launch.
- **🔗 Signed webhooks** (HMAC-SHA256, SSRF-guarded) & **REST API keys** (`Bearer`).
- **⏱️ Scheduling & drip throttle**, a **durable retrying job queue**, and **bulk actions** across every list.
- **⚙️ One-command Docker** with auto-bootstrapped admin, Alembic migrations applied on startup.

## 🚀 Quickstart — one command

```bash
docker compose up --build
```

Then:

1. Open **http://localhost:8080**
2. Grab the first-run admin password from the logs:
   ```bash
   docker compose logs phishsim | grep -A3 "first-run"
   ```
   (or set `PHISHSIM_BOOTSTRAP_ADMIN_PASSWORD` in `docker-compose.yml` to choose your own.)
3. Sign in, set a new password, and go. With the default **console** mail backend, launching a campaign writes each email as a `.eml` file to the data volume instead of sending — so you can walk the whole open → click → submit → teach flow with **zero real email**. Switch `PHISHSIM_MAIL_BACKEND=smtp` and add a Sending Profile to deliver for real (against hosts you're authorized to test).

Data (SQLite + outbox) persists in the `phishsim-data` volume. Use `docker compose up -d` to keep it — **not** `down -v`, which wipes the volume.

## 🧩 Tech stack

| Layer | Stack |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, aiosmtplib, httpx |
| Frontend | React 18 + TypeScript, Vite, hand-rolled SVG charts, CKEditor 5 |
| Security | argon2id hashing, AES-256-GCM column encryption, CSRF, SSRF guard, CSP/HSTS headers |
| Deploy | Multi-stage Docker (node build → python runtime), SQLite volume |

## 🛠️ Local dev (without Docker)

```bash
# Backend (auto-creates an admin, prints the password)
cd backend
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8080 --reload

# Frontend (hot reload, proxies /api → :8080)
cd frontend && npm install && npm run dev
```

Interactive API docs (dev only): `http://localhost:8080/api/docs`

## 🔐 Responsible use

VoltPhish is a *simulation* tool, deliberately built so it can't quietly become a credential-harvesting kit:

- **Submitted passwords are never persisted.** The landing endpoint reads the form and discards the password; by default no submitted field values are stored at all — only that a submission occurred, for your metrics.
- SMTP secrets are **encrypted at rest** (AES-256-GCM) and never returned by the API.
- Every campaign action is recorded in an **append-only audit log**.
- Tracking links use unguessable per-recipient tokens; invalid tokens return a benign response and record nothing.

Only run campaigns against recipients within your authorized scope, and keep a record of that authorization. See [SECURITY.md](SECURITY.md) for the threat model and control mapping.

## 📄 License

[MIT](LICENSE) — do good with it.
