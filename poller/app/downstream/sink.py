"""Downstream sink abstractions for Telegram updates."""
import logging
from typing import Protocol

from app.telegram.types import TelegramUpdate

logger = logging.getLogger(__name__)


class UpdateSink(Protocol):
    """Consumes Telegram updates after they are fetched."""

    async def handle(self, update: TelegramUpdate) -> None:
        """Process a single Telegram update."""


class LoggingUpdateSink:
    """Temporary sink used to validate polling flow before transport integration."""

    async def handle(self, update: TelegramUpdate) -> None:
        update_id = update.get("update_id")
        update_type = next(
            (key for key in update.keys() if key != "update_id"),
            "unknown",
        )
        logger.info(
            "Received Telegram update_id=%s type=%s",
            update_id,
            update_type,
        )
