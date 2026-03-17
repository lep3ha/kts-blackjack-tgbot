from typing import Protocol

from app.state.models import SessionContext


class DedupStore(Protocol):
    async def check_and_mark(self, key: str, ttl_seconds: int) -> bool:
        """Return True when key is new and was marked, False for duplicates."""


class SessionContextStore(Protocol):
    async def get(self, chat_id: str) -> SessionContext | None:
        """Load the latest known session context for chat."""

    async def set(self, chat_id: str, context: SessionContext, ttl_seconds: int) -> None:
        """Persist session context snapshot for chat."""
