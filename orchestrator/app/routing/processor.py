from app.routing.dedup import build_dedup_key
from app.routing.interfaces import CommandDispatcher
from app.routing.models import OrchestratorCommand
from app.routing.models import OrchestratorResult
from app.state.interfaces import DedupStore


class DeduplicatingCommandProcessor:
    def __init__(
        self,
        *,
        dispatcher: CommandDispatcher,
        dedup_store: DedupStore,
        dedup_ttl_seconds: int,
    ) -> None:
        self._dispatcher = dispatcher
        self._dedup_store = dedup_store
        self._dedup_ttl_seconds = dedup_ttl_seconds

    async def process(self, command: OrchestratorCommand) -> OrchestratorResult:
        dedup_key = build_dedup_key(command)
        is_new = await self._dedup_store.check_and_mark(
            dedup_key,
            ttl_seconds=self._dedup_ttl_seconds,
        )
        if not is_new:
            return OrchestratorResult(
                success=True,
                command_type=command.command_type,
                message="Duplicate command skipped",
                error_code="duplicate_skipped",
            )

        return await self._dispatcher.dispatch(command)
