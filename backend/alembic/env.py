"""Alembic environment. Uses the app's engine/metadata and settings URL."""
from __future__ import annotations

from alembic import context

from app.config import get_settings
from app.database import Base, engine
from app.models.base import UTCDateTime
from app import models  # noqa: F401  (register all tables on Base.metadata)

config = context.config
target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", get_settings().database_url)


def render_item(type_, obj, autogen_context):
    """Render the custom UTCDateTime as a plain sa.DateTime in migrations so the
    generated files don't depend on app internals."""
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime()"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,  # SQLite-friendly ALTERs
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
            render_item=render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
