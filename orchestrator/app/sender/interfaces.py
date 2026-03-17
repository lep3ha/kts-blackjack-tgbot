from typing import Protocol

from app.sender.models import UiKeyboard


class SenderService(Protocol):
    async def send_text(
        self,
        *,
        chat_id: str,
        text: str,
        keyboard: UiKeyboard | None = None,
    ) -> int | None:
        """Send a message to Telegram chat. Returns Telegram message_id or None."""

    async def delete_message(
        self,
        *,
        chat_id: str,
        message_id: int,
    ) -> None:
        """Delete a previously sent message. Silently ignores failures."""

    async def set_my_commands(self, commands: list[dict[str, str]]) -> None:
        """Configure Telegram command menu for the bot."""