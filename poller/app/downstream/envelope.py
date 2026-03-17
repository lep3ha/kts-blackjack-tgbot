"""Builders for downstream broker envelopes."""
from datetime import datetime
from datetime import timezone

from app.downstream.contracts import TelegramUpdateEnvelope
from app.runtime.partitioning import resolve_source_key
from app.telegram.types import TelegramUpdate


def build_update_envelope(
    update: TelegramUpdate,
    received_at: datetime | None = None,
) -> TelegramUpdateEnvelope:
    """Build a validated downstream envelope for a Telegram update."""
    update_id = update.get("update_id")
    if not isinstance(update_id, int):
        raise ValueError("Telegram update must contain integer update_id")

    source_key = resolve_source_key(update)
    return TelegramUpdateEnvelope(
        update_id=update_id,
        update_type=resolve_update_type(update),
        source_key=source_key,
        partition_key=source_key,
        next_offset=update_id + 1,
        received_at=received_at or datetime.now(timezone.utc),
        payload=update,
    )


def resolve_update_type(update: TelegramUpdate) -> str:
    """Resolve the top-level Telegram update type."""
    return next(
        (key for key in update.keys() if key != "update_id"),
        "unknown",
    )