import logging

from app.routing.game_client import GameServiceClient
from app.routing.game_client.models import TimeoutTurnRequest
from app.sender.interfaces import SenderService
from app.sender.presenter import present_orchestrator_result
from app.routing.models import OrchestratorResult
from app.timers.models import TimeoutTask


logger = logging.getLogger(__name__)


class GameServiceTimeoutExecutor:
    def __init__(self, game_client: GameServiceClient, sender: SenderService) -> None:
        self._game_client = game_client
        self._sender = sender

    async def execute_timeout(self, task: TimeoutTask) -> None:
        envelope = await self._game_client.timeout_turn(
            TimeoutTurnRequest(
                chat_id=task.chat_id,
                chat_type=task.chat_type if task.chat_type in {"group", "single"} else "group",
                turn_version=task.turn_version,
                hand_index=task.hand_index,
            )
        )

        if not envelope.success:
            return

        try:
            data = envelope.data if isinstance(envelope.data, dict) else {}
            current_player = data.get("current_player")
            if current_player and current_player.get("participant_status") in {"inactive", "settled"}:
                return
            
            result = OrchestratorResult(
                success=envelope.success,
                command_type="player_action",
                message="timeout",
                data={**data, "_timeout": True} if data else {"_timeout": True},
            )
            outbound = present_orchestrator_result(
                task.chat_id,
                result,
                chat_type=task.chat_type,
            )
            notice = "⏰ Время вышло — ход засчитан как Stand."
            outbound_text = f"{notice}\n\n{outbound.text}"
            await self._sender.send_text(
                chat_id=task.chat_id,
                text=outbound_text,
                keyboard=outbound.keyboard,
                parse_mode=outbound.parse_mode,
            )
        except Exception:
            logger.exception("Failed to send timeout notification chat_id=%s", task.chat_id)
