"""Shared model helpers."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    """Timezone-aware UTC now. Use everywhere instead of naive datetimes."""
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """A DateTime that always stores/returns tz-aware UTC.

    SQLite (and some drivers) drop tzinfo on round-trip, which then breaks
    aware/naive comparisons. This normalizes on the way in and out so the rest
    of the app can assume every datetime is aware UTC.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
