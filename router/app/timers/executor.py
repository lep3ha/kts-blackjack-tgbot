from app.game_client import GameServiceClient
from app.game_client.models import TimeoutTurnRequest
from app.timers.models import TimeoutTask


class GameServiceTimeoutExecutor:
    def __init__(self, game_client: GameServiceClient) -> None:
        self._game_client = game_client

    async def execute_timeout(self, task: TimeoutTask) -> None:
        await self._game_client.timeout_turn(
            TimeoutTurnRequest(
                chat_id=task.chat_id,
                chat_type=task.chat_type if task.chat_type in {"group", "single"} else "group",
                turn_version=task.turn_version,
            )
        )
