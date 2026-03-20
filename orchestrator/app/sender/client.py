import logging
from typing import Any

import aiohttp

from app.sender.interfaces import SenderService
from app.sender.models import ParseMode
from app.sender.models import UiKeyboard
from app.sender.renderers import render_keyboard_markup


logger = logging.getLogger(__name__)


class TelegramSenderError(RuntimeError):
    """Raised when Telegram API call fails."""


class TelegramSenderClient(SenderService):
    def __init__(
        self,
        *,
        base_url: str,
        bot_token: str,
        request_timeout_seconds: float,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._bot_token = bot_token
        self._timeout = aiohttp.ClientTimeout(total=request_timeout_seconds)
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> "TelegramSenderClient":
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def send_text(
        self,
        *,
        chat_id: str,
        text: str,
        keyboard: UiKeyboard | None = None,
        parse_mode: ParseMode | None = None,
    ) -> int | None:
        if not self._bot_token:
            raise TelegramSenderError("TELEGRAM_BOT_TOKEN is empty")

        session = self._require_session()
        url = f"{self._base_url}/bot{self._bot_token}/sendMessage"

        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        reply_markup = render_keyboard_markup(keyboard)
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode

        try:
            async with session.post(url, json=payload) as response:
                response_payload = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise TelegramSenderError("Telegram sendMessage request failed") from exc

        if not isinstance(response_payload, dict):
            raise TelegramSenderError("Telegram API returned non-object payload")

        if response_payload.get("ok") is True:
            result = response_payload.get("result")
            if isinstance(result, dict):
                msg_id = result.get("message_id")
                if isinstance(msg_id, int):
                    return msg_id
            return None

        description = str(response_payload.get("description", "Unknown Telegram API error"))
        raise TelegramSenderError(description)

    async def delete_message(
        self,
        *,
        chat_id: str,
        message_id: int,
    ) -> None:
        """Call Telegram deleteMessage. Silently discards any errors."""
        if not self._bot_token:
            return

        session = self._require_session()
        url = f"{self._base_url}/bot{self._bot_token}/deleteMessage"
        payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id}

        try:
            async with session.post(url, json=payload) as response:
                await response.read()
        except Exception:
            logger.debug("deleteMessage failed chat_id=%s message_id=%s", chat_id, message_id)

    async def set_my_commands(self, commands: list[dict[str, str]]) -> None:
        if not self._bot_token:
            raise TelegramSenderError("TELEGRAM_BOT_TOKEN is empty")

        session = self._require_session()
        url = f"{self._base_url}/bot{self._bot_token}/setMyCommands"
        payload: dict[str, Any] = {"commands": commands}

        try:
            async with session.post(url, json=payload) as response:
                response_payload = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise TelegramSenderError("Telegram setMyCommands request failed") from exc

        if not isinstance(response_payload, dict):
            raise TelegramSenderError("Telegram API returned non-object payload")

        if response_payload.get("ok") is True:
            return

        description = str(response_payload.get("description", "Unknown Telegram API error"))
        raise TelegramSenderError(description)

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is not None:
            return self._session

        self._session = aiohttp.ClientSession(timeout=self._timeout)
        self._owns_session = True
        return self._session
