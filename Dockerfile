# ─────────────────────────────────────────────────────────────
# VoltPhish — single-image build. Like Gophish, one container runs
# the whole thing: the React admin UI is compiled and served by the
# FastAPI backend. No separate frontend process.
# ─────────────────────────────────────────────────────────────

# ---- Stage 1: build the React admin SPA ----
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # -> /frontend/dist

# ---- Stage 2: Python runtime that serves API + tracking + SPA ----
FROM python:3.12-slim AS runtime

# Run as an unprivileged user (CLAUDE.md A05).
RUN useradd --create-home --uid 10001 voltphish
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend /frontend/dist ./static

# Persist DB + mail outbox under /data (mount a volume here).
ENV VOLTPHISH_STATIC_DIR=/app/static \
    VOLTPHISH_DATABASE_URL=sqlite+pysqlite:////data/voltphish.db \
    VOLTPHISH_MAIL_OUTBOX=/data/outbox \
    VOLTPHISH_ENV=development

RUN mkdir -p /data && chown -R voltphish:voltphish /data /app
USER voltphish

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=4s --start-period=8s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
