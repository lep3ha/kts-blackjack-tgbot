from typing import Protocol

from app.routing.models import RouterCommand
from app.routing.models import RouterResult
from app.state.models import SessionContext


class CommandDispatcher(Protocol):
    async def dispatch(self, command: RouterCommand) -> RouterResult:
        """Route a normalized command to the appropriate domain handler."""


class UpdateNormalizer(Protocol):
    def normalize(
        self,
        envelope: "TelegramUpdateEnvelope",
        *,
        context: SessionContext | None = None,
    ) -> RouterCommand:
        """Normalize upstream envelope into internal command model."""
