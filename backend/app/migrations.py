"""Run Alembic migrations programmatically on startup.

Adoption logic so upgrades are safe for any starting state:
  - fresh DB (no tables)               -> upgrade to head (creates everything)
  - DB predating Alembic (has tables,
    no alembic_version)                -> stamp head (baseline the existing
                                          schema), then upgrade for anything new
  - already Alembic-managed            -> upgrade to head (apply pending)
"""
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .config import get_settings
from .database import engine

log = logging.getLogger("phishsim.migrations")

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    return cfg


def run_migrations() -> None:
    cfg = _alembic_config()
    tables = set(inspect(engine).get_table_names())

    if "alembic_version" in tables:
        command.upgrade(cfg, "head")
    elif tables:
        # Pre-Alembic schema (created by an earlier create_all build). Baseline
        # it as head, then apply anything newer.
        log.info("adopting existing schema into Alembic (stamp head)")
        command.stamp(cfg, "head")
        command.upgrade(cfg, "head")
    else:
        command.upgrade(cfg, "head")
    log.info("database migrations applied")
