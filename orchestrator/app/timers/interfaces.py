from datetime import datetime
from typing import Protocol

from app.timers.models import TimeoutTask


class TimerScheduler(Protocol):
    async def schedule_timeout(
        self,
        *,
        chat_id: str,
        chat_type: str,
        session_id: int,
        turn_version: int,
        hand_index: int | None = None,
        due_at: datetime,
    ) -> None:
        """Schedule a timeout call for a specific turn."""

    async def cancel_timeout(self, *, chat_id: str, session_id: int, turn_version: int) -> None:
        """Cancel timeout task for a specific turn if it exists."""


class TimeoutExecutor(Protocol):
    async def execute_timeout(self, task: TimeoutTask) -> None:
        """Execute timeout side effect for the provided task."""


class TimerWorker(TimerScheduler, Protocol):
    async def start(self) -> None:
        """Start background timer processing."""

    async def stop(self) -> None:
        """Stop background timer processing."""
