"""Bounded intake queue for Telegram updates."""
import asyncio
from dataclasses import dataclass
from typing import Final

from app.telegram.types import TelegramUpdate

_QUEUE_SENTINEL: Final = object()


@dataclass(slots=True)
class QueuedUpdate:
    """Telegram update enqueued for downstream processing."""

    sequence_number: int
    update: TelegramUpdate
    next_offset: int | None


class BoundedUpdateQueue:
    """Async bounded queue for buffering Telegram updates."""

    def __init__(self, max_size: int) -> None:
        if max_size <= 0:
            raise ValueError("Queue size must be greater than zero")

        self._queue: asyncio.Queue[QueuedUpdate | object] = asyncio.Queue(maxsize=max_size)

    @property
    def max_size(self) -> int:
        """Return the configured queue capacity."""
        return self._queue.maxsize

    def qsize(self) -> int:
        """Return current queue size."""
        return self._queue.qsize()

    def is_full(self) -> bool:
        """Return whether the queue is currently full."""
        return self._queue.full()

    async def put(self, item: QueuedUpdate) -> None:
        """Put a new update into the queue."""
        await self._queue.put(item)

    async def get(self) -> QueuedUpdate | None:
        """Get the next queued update or queue close sentinel."""
        item = await self._queue.get()
        if item is _QUEUE_SENTINEL:
            self._queue.task_done()
            return None
        return item

    def task_done(self) -> None:
        """Mark the current queued item as processed."""
        self._queue.task_done()

    async def join(self) -> None:
        """Wait until all queued items are processed."""
        await self._queue.join()

    async def close(self, consumer_count: int = 1) -> None:
        """Signal queue consumers to stop."""
        for _ in range(consumer_count):
            await self._queue.put(_QUEUE_SENTINEL)
