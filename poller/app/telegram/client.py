"""Telegram Bot API long-polling client."""
import asyncio
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError
from aiohttp import ClientSession
from aiohttp import ClientTimeout

from app.telegram.errors import FatalTelegramError
from app.telegram.errors import RetryableTelegramError
from app.telegram.errors import is_retryable_status
from app.telegram.types import TelegramUpdate


@dataclass(slots=True)
class RetryPolicy:
    """Exponential backoff policy for retryable polling errors."""

    base_delay: float
    max_delay: float

    def next_delay(
        self,
        attempt: int,
        retry_after: float | None = None,
    ) -> float:
        """Calculate the next retry delay."""
        if retry_after is not None:
            return min(retry_after, self.max_delay)

        delay = self.base_delay * (2 ** max(attempt, 0))
        return min(delay, self.max_delay)


class TelegramPollingClient:
    """Client for Telegram getUpdates long polling."""

    def __init__(
        self,
        bot_token: str,
        base_url: str,
        poll_timeout: int,
        poll_limit: int,
        request_timeout: int,
        retry_policy: RetryPolicy,
    ) -> None:
        self.bot_token = bot_token
        self.base_url = base_url.rstrip("/")
        self.poll_timeout = poll_timeout
        self.poll_limit = poll_limit
        self.request_timeout = request_timeout
        self.retry_policy = retry_policy

    async def fetch_updates(
        self,
        session: ClientSession,
        offset: int | None,
    ) -> list[TelegramUpdate]:
        """Fetch updates from Telegram Bot API."""
        payload: dict[str, Any] = {
            "timeout": self.poll_timeout,
            "limit": self.poll_limit,
        }
        if offset is not None:
            payload["offset"] = offset

        request_timeout = ClientTimeout(total=self.request_timeout)
        endpoint = f"{self.base_url}/bot{self.bot_token}/getUpdates"

        try:
            async with session.post(
                endpoint,
                json=payload,
                timeout=request_timeout,
            ) as response:
                if is_retryable_status(response.status):
                    raise RetryableTelegramError(
                        message=(
                            f"Retryable Telegram HTTP status received: {response.status}"
                        )
                    )

                if response.status >= 400:
                    body = await response.text()
                    raise FatalTelegramError(
                        f"Telegram HTTP error {response.status}: {body}"
                    )

                result = await response.json()
        except asyncio.TimeoutError as error:
            raise RetryableTelegramError("Telegram request timed out") from error
        except ClientError as error:
            raise RetryableTelegramError("Telegram network error") from error

        return self._parse_updates(result)

    def _parse_updates(self, payload: dict[str, Any]) -> list[TelegramUpdate]:
        """Validate Telegram Bot API payload."""
        if payload.get("ok") is True:
            updates = payload.get("result", [])
            if not isinstance(updates, list):
                raise FatalTelegramError("Telegram payload 'result' must be a list")
            return updates

        error_code = payload.get("error_code")
        description = payload.get("description", "Unknown Telegram API error")
        parameters = payload.get("parameters") or {}
        retry_after = parameters.get("retry_after")

        if isinstance(error_code, int) and is_retryable_status(error_code):
            raise RetryableTelegramError(
                message=f"Retryable Telegram API error: {description}",
                retry_after=float(retry_after) if retry_after is not None else None,
            )

        raise FatalTelegramError(f"Telegram API error: {description}")
