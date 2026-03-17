"""Telegram polling error primitives."""
from dataclasses import dataclass


class TelegramPollingError(Exception):
    """Base exception for polling errors."""


class FatalTelegramError(TelegramPollingError):
    """Non-retryable Telegram API error."""


@dataclass(slots=True)
class RetryableTelegramError(TelegramPollingError):
    """Retryable Telegram API error with optional retry hint."""

    message: str
    retry_after: float | None = None

    def __str__(self) -> str:
        return self.message


def is_retryable_status(status_code: int) -> bool:
    """Return whether a Telegram HTTP status should be retried."""
    return status_code == 429 or status_code >= 500
