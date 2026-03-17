"""Offset store abstractions for Telegram polling."""
import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Protocol

logger = logging.getLogger(__name__)


class OffsetStore(Protocol):
    """Persistent contract for confirmed Telegram offsets."""

    async def load_offset(self) -> int | None:
        """Load the last confirmed offset."""

    async def save_offset(self, offset: int) -> None:
        """Persist the last confirmed offset."""


class InMemoryOffsetStore:
    """Temporary offset store used until durable storage is introduced."""

    def __init__(self, initial_offset: int | None = None) -> None:
        self._offset = initial_offset

    async def load_offset(self) -> int | None:
        return self._offset

    async def save_offset(self, offset: int) -> None:
        self._offset = offset


class FileOffsetStore:
    """JSON-backed offset store with atomic file replacement."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def load_offset(self) -> int | None:
        try:
            offset = await asyncio.to_thread(self._load_offset_sync)
        except Exception:
            logger.exception("Failed to load offset state from %s", self._path)
            raise

        if offset is None:
            logger.info("Offset state file not found, starting without stored offset: %s", self._path)
        else:
            logger.info("Loaded offset=%s from state file %s", offset, self._path)

        return offset

    async def save_offset(self, offset: int) -> None:
        try:
            await asyncio.to_thread(self._save_offset_sync, offset)
        except Exception:
            logger.exception("Failed to save offset=%s into state file %s", offset, self._path)
            raise

        logger.info("Saved offset=%s into state file %s", offset, self._path)

    def _load_offset_sync(self) -> int | None:
        if not self._path.exists():
            return None

        with self._path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        offset = payload.get("offset")
        if not isinstance(offset, int) or offset < 0:
            raise ValueError("Offset state file must contain non-negative integer 'offset'")

        return offset

    def _save_offset_sync(self, offset: int) -> None:
        if offset < 0:
            raise ValueError("Offset must be a non-negative integer")

        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._path.parent,
                prefix=f"{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                json.dump({"offset": offset}, temp_file)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_path = Path(temp_file.name)

            os.replace(temp_path, self._path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()


OffsetStoreFactory = Callable[[], Awaitable[OffsetStore] | OffsetStore]
