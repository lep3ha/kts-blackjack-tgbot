"""Offset commit coordination for concurrent update processing."""
import asyncio


class OffsetCommitTracker:
    """Tracks contiguous acknowledgements and returns committable offsets."""

    def __init__(self, initial_offset: int | None = None) -> None:
        self._lock = asyncio.Lock()
        self._next_sequence = 1
        self._completed: dict[int, int | None] = {}
        self._last_committed_offset = initial_offset

    async def mark_processed(
        self,
        sequence_number: int,
        next_offset: int | None,
    ) -> int | None:
        """Record a processed sequence and return the highest committable offset."""
        async with self._lock:
            self._completed[sequence_number] = next_offset
            committable_offset: int | None = None

            while self._next_sequence in self._completed:
                candidate_offset = self._completed.pop(self._next_sequence)
                if candidate_offset is not None:
                    self._last_committed_offset = candidate_offset
                    committable_offset = candidate_offset
                self._next_sequence += 1

            return committable_offset
