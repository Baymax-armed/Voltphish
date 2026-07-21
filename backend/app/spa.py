"""Serve the built React admin SPA from the backend (single-process deploy).

The compiled frontend lives at VOLTPHISH_STATIC_DIR (default: ../frontend/dist,
or /app/static in Docker). Hashed asset files are served directly; any other
non-API, non-tracking path falls back to index.html so client-side routing works
on deep links / refresh.

If the build hasn't been produced yet, we mount nothing and log a hint — the API
still works; only the UI is absent.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("voltphish.spa")


def _static_dir() -> Path:
    env = os.environ.get("VOLTPHISH_STATIC_DIR")
    if env:
        return Path(env)
    # default: repo-relative frontend/dist
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def mount_spa(app: FastAPI) -> None:
    dist = _static_dir()
    index = dist / "index.html"
    if not index.is_file():
        log.warning(
            "SPA build not found at %s — UI disabled (API/docs still available). "
            "Build the frontend (npm run build) or run via Docker.",
            dist,
        )
        return

    # Serve hashed assets (JS/CSS/img) with long-lived caching.
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    # Path prefixes owned by the API / tracking / add-in servers — never the SPA.
    # NOTE: use a trailing "/" (or an exact match) so a prefix like "report"
    # doesn't also swallow SPA routes such as "reported".
    _reserved = ("api/", "t/", "c/", "p/", "q/", "a/", "r/", "s/", "learn/", "report/", "addins/", "train/", "assets/")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str, request: Request):
        # Never shadow the API or the tracking server.
        if full_path == "report" or full_path.startswith(_reserved):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        # Serve a real file if one exists (favicon, etc.), else the SPA shell.
        candidate = dist / full_path
        if full_path and candidate.is_file() and candidate.resolve().is_relative_to(dist.resolve()):
            return FileResponse(str(candidate))
        return FileResponse(str(index))

    log.info("Serving admin SPA from %s", dist)
