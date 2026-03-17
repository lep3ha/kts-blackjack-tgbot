"""Datetime helpers used across the service."""
from __future__ import annotations

from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    """Return current UTC time as naive datetime for timestamp-without-time-zone columns."""
    return datetime.now(UTC).replace(tzinfo=None)
