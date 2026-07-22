# Contributing to VoltPhish

Thanks for wanting to help! VoltPhish is a defensive, **authorized-use-only**
security-awareness tool — contributions should keep it that way.

## Ground rules

- **Defensive only.** We build simulation & training features. We do **not** accept
  offensive capabilities (live MFA-bypass/session-proxying, real-brand credential
  harvesting, detection evasion, etc.).
- **Secure by default.** No hardcoded secrets, parameterized queries only, validate
  input on the server, never store submitted passwords. See [SECURITY.md](SECURITY.md).
- Be kind in issues and reviews.

## Dev setup

```bash
# Backend (auto-creates an admin, prints the password)
cd backend
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8010 --reload

# Frontend (hot reload, proxies /api → :8010)
cd frontend && npm install && npm run dev
```

Or just `docker compose up --build`.

## Before you open a PR

- Run the tests: `cd backend && python -m pytest -q` (they must stay green).
- Add a test for new behavior — happy path **and** at least one abuse case.
- New DB change? Add an Alembic migration under `backend/alembic/versions/`.
- Keep the diff focused; match the surrounding style.

## Good first issues

- New email templates for the gallery (`frontend/src/gallery.ts`).
- Additional training modules (`backend/app/services/training_seed.py`).
- Localization / translations.
- Docs & screenshots.

## Reporting security issues

Please **don't** open a public issue for vulnerabilities. See [SECURITY.md](SECURITY.md)
for private disclosure.
