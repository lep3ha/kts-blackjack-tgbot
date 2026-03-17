"""Downstream sink abstractions for Telegram updates."""
from typing import Protocol

from app.telegram.types import TelegramUpdate


class UpdateSink(Protocol):
    """Consumes Telegram updates after they are fetched."""

    async def handle(self, update: TelegramUpdate) -> None:
        """Process a single Telegram update."""
