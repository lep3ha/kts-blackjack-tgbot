import asyncio
import json
from pathlib import Path

import pytest

from app.storage.offset_store import FileOffsetStore


def test_file_offset_store_roundtrip(tmp_path: Path) -> None:
    async def scenario() -> None:
        state_path = tmp_path / "state" / "offset.json"
        store = FileOffsetStore(state_path)

        assert await store.load_offset() is None
        await store.save_offset(42)
        assert await store.load_offset() == 42

        payload = json.loads(state_path.read_text(encoding="utf-8"))
        assert payload == {"offset": 42}

    asyncio.run(scenario())


def test_file_offset_store_rejects_negative_offset(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = FileOffsetStore(tmp_path / "offset.json")
        with pytest.raises(ValueError):
            await store.save_offset(-1)

    asyncio.run(scenario())
