from typing import Protocol

from app.routing.models import OrchestratorCommand
from app.routing.models import OrchestratorResult
from app.state.models import SessionContext


class CommandDispatcher(Protocol):
    async def dispatch(self, command: OrchestratorCommand) -> OrchestratorResult:
        """Route a normalized command to the appropriate domain handler."""


class UpdateNormalizer(Protocol):
    def normalize(
        self,
        envelope: "TelegramUpdateEnvelope",
        *,
        context: SessionContext | None = None,
    ) -> OrchestratorCommand:
        """Normalize upstream envelope into internal command model."""
