"""PhishSim application entrypoint.

Mounts, on one app:
  - the authenticated admin API under /api/v1/*
  - the public phishing/tracking server at the root (/t, /c, /p, /r)

Run:  uvicorn app.main:app --host 127.0.0.1 --port 8080
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .bootstrap import ensure_admin, ensure_dev_smtp_profile
from .config import get_settings
from .database import init_db
from .middleware import SecurityHeadersMiddleware
from .phish import server as phish_server
from .routers import (
    apikeys,
    auth,
    campaigns,
    dashboard,
    deliverability,
    groups,
    pages,
    profiles,
    settings as settings_router,
    sms_profiles,
    templates,
    testmail,
    users,
    webhooks,
)
from .services.queue import start_workers, stop_workers
from .services.scheduler import start_scheduler, stop_scheduler
from .spa import mount_spa

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("phishsim")
settings = get_settings()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    ensure_admin()
    ensure_dev_smtp_profile()
    start_workers()
    start_scheduler()
    log.info("VoltPhish started (env=%s, mail_backend=%s)", settings.env.value, settings.mail_backend.value)
    yield
    stop_scheduler()
    stop_workers()


app = FastAPI(
    title="VoltPhish",
    version="0.1.0",
    description="Phishing simulation for authorized security-awareness training.",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Never leak internals to the client (§7). Full detail goes to logs.
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# Authenticated admin API
app.include_router(auth.router)
app.include_router(templates.router)
app.include_router(groups.router)
app.include_router(profiles.router)
app.include_router(sms_profiles.router)
app.include_router(pages.router)
app.include_router(campaigns.router)
app.include_router(testmail.router)
app.include_router(users.router)
app.include_router(webhooks.router)
app.include_router(apikeys.router)
app.include_router(settings_router.router)
app.include_router(dashboard.router)
app.include_router(deliverability.router)

# Public phishing/tracking server (unauthenticated by design)
app.include_router(phish_server.router)

# Built admin SPA + client-side routing fallback. Registered LAST so its
# catch-all never shadows the API or the tracking routes above.
mount_spa(app)
