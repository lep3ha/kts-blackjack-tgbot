from collections.abc import Awaitable
from collections.abc import Callable

from app.routing.game_client import GameServiceClient
from app.routing.game_client.models import CurrentSessionRequest
from app.routing.game_client.models import GameErrorCode
from app.routing.game_client.models import GameServiceEnvelope
from app.routing.game_client.models import RegisterPlayerRequest
from app.routing.models import OrchestratorCommand
from app.routing.models import OrchestratorResult
from app.state.interfaces import SessionContextStore
from app.state.models import SessionContext

from .constants import DEFAULT_BET
from .constants import DEFAULT_REGISTER_BANK


class BaseCommandHandlers:
    def __init__(
        self,
        game_client: GameServiceClient,
        *,
        session_context_store: SessionContextStore | None = None,
        context_ttl_seconds: int = 7200,
    ) -> None:
        self._game_client = game_client
        self._session_context_store = session_context_store
        self._context_ttl_seconds = context_ttl_seconds

    @staticmethod
    def _resolve_bet(bet: int | None) -> int:
        return bet if bet is not None else DEFAULT_BET

    @staticmethod
    def _resolve_register_bank(bank: int | None) -> int:
        return bank if bank is not None else DEFAULT_REGISTER_BANK

    async def _execute_with_auto_register(
        self,
        *,
        command: OrchestratorCommand,
        request: Callable[[], Awaitable[GameServiceEnvelope]],
    ) -> GameServiceEnvelope | OrchestratorResult:
        try:
            envelope = await request()
        except Exception:
            return self._request_failed_result(command)

        if not self._should_auto_register(command=command, envelope=envelope):
            return envelope

        try:
            register_envelope = await self._game_client.register_player(
                RegisterPlayerRequest(
                    telegram_id=command.actor_telegram_id,
                    username=command.actor_username,
                    first_name=command.actor_first_name,
                    bank=DEFAULT_REGISTER_BANK,
                )
            )
        except Exception:
            return self._request_failed_result(command)

        if (
            not register_envelope.success
            and (
                register_envelope.error is None
                or register_envelope.error.code != GameErrorCode.STATE_CONFLICT
            )
        ):
            return register_envelope

        try:
            return await request()
        except Exception:
            return self._request_failed_result(command)

    @staticmethod
    def _should_auto_register(
        *,
        command: OrchestratorCommand,
        envelope: GameServiceEnvelope,
    ) -> bool:
        if command.actor_telegram_id is None:
            return False

        if command.command_type == "player_register":
            return False

        return (
            not envelope.success
            and envelope.error is not None
            and envelope.error.code == GameErrorCode.NOT_FOUND
        )

    async def _check_stale_before_action(self, command: OrchestratorCommand) -> OrchestratorResult | None:
        if self._session_context_store is None:
            return None

        context = await self._session_context_store.get(command.chat_id)
        if context is None or context.turn_version is None:
            return None

        if command.turn_version == context.turn_version:
            return None

        return OrchestratorResult(
            success=False,
            command_type=command.command_type,
            message=(
                "stale_turn: local guard blocked action "
                f"command_turn={command.turn_version} context_turn={context.turn_version}"
            ),
            error_code=GameErrorCode.STALE_TURN.value,
        )

    async def _check_turn_owner_before_action(self, command: OrchestratorCommand) -> OrchestratorResult | None:
        if self._session_context_store is None:
            return None

        context = await self._session_context_store.get(command.chat_id)
        if context is None or context.current_player_telegram_id is None:
            return None

        if context.current_player_telegram_id == command.actor_telegram_id:
            return None

        return OrchestratorResult(
            success=False,
            command_type=command.command_type,
            message="not_your_turn: local guard blocked action for non-current player",
            error_code="not_your_turn",
        )

    async def _check_available_moves_before_action(self, command: OrchestratorCommand) -> OrchestratorResult | None:
        if self._session_context_store is None:
            return None

        context = await self._session_context_store.get(command.chat_id)
        if context is None or not context.available_moves:
            return None

        if command.action in context.available_moves:
            return None

        return OrchestratorResult(
            success=False,
            command_type=command.command_type,
            message=(
                "invalid_local_action: local guard blocked action "
                f"action={command.action} available={context.available_moves}"
            ),
            error_code="invalid_local_action",
        )

    async def _refresh_context(self, command: OrchestratorCommand) -> None:
        if self._session_context_store is None:
            return

        try:
            envelope = await self._game_client.current_session(
                CurrentSessionRequest(
                    chat_id=command.chat_id,
                    chat_type=command.chat_type,
                )
            )
        except Exception:
            return

        await self._update_context_from_envelope(command=command, envelope=envelope)

    @staticmethod
    def _request_failed_result(command: OrchestratorCommand) -> OrchestratorResult:
        return OrchestratorResult(
            success=False,
            command_type=command.command_type,
            message="Игровой сервис временно недоступен. Попробуй снова через несколько секунд.",
            error_code="transport_error",
        )

    async def _update_context_from_envelope(
        self,
        *,
        command: OrchestratorCommand,
        envelope: GameServiceEnvelope,
    ) -> None:
        if self._session_context_store is None:
            return

        context = self._extract_context(command=command, envelope=envelope)
        if context is None:
            return

        await self._session_context_store.set(
            command.chat_id,
            context,
            ttl_seconds=self._context_ttl_seconds,
        )

    @staticmethod
    def _extract_context(
        *,
        command: OrchestratorCommand,
        envelope: GameServiceEnvelope,
    ) -> SessionContext | None:
        if not envelope.success or not isinstance(envelope.data, dict):
            return None

        data = envelope.data
        current_player_telegram_id: str | None = None
        current_player = data.get("current_player")
        if isinstance(current_player, dict):
            player_id = current_player.get("telegram_id")
            if player_id is not None:
                current_player_telegram_id = str(player_id)

        available_moves_raw = data.get("available_moves")
        available_moves: list[str] = []
        if isinstance(available_moves_raw, list):
            available_moves = [str(move) for move in available_moves_raw]

        session_id_raw = data.get("session_id")
        session_id = session_id_raw if isinstance(session_id_raw, int) else None

        turn_version_raw = data.get("turn_version")
        turn_version = turn_version_raw if isinstance(turn_version_raw, int) else None

        current_hand_index_raw = data.get("current_hand_index")
        current_hand_index = current_hand_index_raw if isinstance(current_hand_index_raw, int) else None
        if current_hand_index is None and isinstance(current_player, dict):
            current_player_hand_index = current_player.get("hand_index")
            if isinstance(current_player_hand_index, int):
                current_hand_index = current_player_hand_index

        current_timer_raw = data.get("current_timer")
        current_timer = str(current_timer_raw) if current_timer_raw is not None else None

        return SessionContext(
            chat_id=command.chat_id,
            chat_type=command.chat_type,
            session_id=session_id,
            turn_version=turn_version,
            current_hand_index=current_hand_index,
            current_timer=current_timer,
            current_player_telegram_id=current_player_telegram_id,
            available_moves=available_moves,
        )

    @staticmethod
    def _to_result(command: OrchestratorCommand, envelope: object) -> OrchestratorResult:
        if not isinstance(envelope, GameServiceEnvelope):
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="Invalid game-service response",
                error_code="transport_error",
            )

        if envelope.success:
            return OrchestratorResult(
                success=True,
                command_type=command.command_type,
                message="ok",
                data=envelope.data,
            )

        error_message = envelope.error.message if envelope.error is not None else "game call failed"
        error_code = envelope.error.code.value if envelope.error is not None else "unknown"
        return OrchestratorResult(
            success=False,
            command_type=command.command_type,
            message=error_message,
            error_code=error_code,
            data=envelope.data,
        )
