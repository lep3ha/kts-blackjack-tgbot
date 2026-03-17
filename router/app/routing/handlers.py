from collections.abc import Awaitable
from collections.abc import Callable

from app.game_client import GameServiceClient
from app.game_client.models import CurrentSessionRequest
from app.game_client.models import AdminBanRequest
from app.game_client.models import AdminTopupRequest
from app.game_client.models import GameErrorCode
from app.game_client.models import GameServiceEnvelope
from app.game_client.models import GroupJoinRequest
from app.game_client.models import GroupOpenRequest
from app.game_client.models import GroupStartRequest
from app.game_client.models import PlayerActionRequest
from app.game_client.models import RegisterPlayerRequest
from app.game_client.models import SingleStartRequest
from app.game_client.models import SingleStopRequest
from app.routing.models import RouterCommand
from app.routing.models import RouterResult
from app.state.interfaces import SessionContextStore
from app.state.models import SessionContext


DEFAULT_BET = 100
DEFAULT_REGISTER_BANK = 1000
ADMIN_TELEGRAM_ID = "742099182"


class GameCommandHandlers:
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

    async def handle_tutorial(self, command: RouterCommand) -> RouterResult:
        return RouterResult(
            success=True,
            command_type=command.command_type,
            message="ok",
            data={"chat_type": command.chat_type},
        )

    async def handle_group_open(self, command: RouterCommand) -> RouterResult:
        if command.actor_telegram_id is None:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for group_open",
                error_code="bad_request",
            )

        async def _request() -> GameServiceEnvelope:
            return await self._game_client.group_open(
                GroupOpenRequest(
                    chat_id=command.chat_id,
                    actor_telegram_id=command.actor_telegram_id,
                    actor_username=command.actor_username,
                    actor_first_name=command.actor_first_name,
                    bet=self._resolve_bet(command.bet),
                )
            )

        envelope = await self._execute_with_auto_register(command=command, request=_request)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_group_start(self, command: RouterCommand) -> RouterResult:
        if command.actor_telegram_id is None:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for group_start",
                error_code="bad_request",
            )

        async def _request() -> GameServiceEnvelope:
            return await self._game_client.group_start(
                GroupStartRequest(
                    chat_id=command.chat_id,
                    actor_telegram_id=command.actor_telegram_id,
                    actor_username=command.actor_username,
                    actor_first_name=command.actor_first_name,
                )
            )

        envelope = await self._execute_with_auto_register(command=command, request=_request)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_group_join(self, command: RouterCommand) -> RouterResult:
        if command.actor_telegram_id is None:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for group_join",
                error_code="bad_request",
            )

        async def _request() -> GameServiceEnvelope:
            return await self._game_client.group_join(
                GroupJoinRequest(
                    chat_id=command.chat_id,
                    actor_telegram_id=command.actor_telegram_id,
                    actor_username=command.actor_username,
                    actor_first_name=command.actor_first_name,
                    bet=self._resolve_bet(command.bet),
                )
            )

        envelope = await self._execute_with_auto_register(command=command, request=_request)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_single_start(self, command: RouterCommand) -> RouterResult:
        if command.actor_telegram_id is None:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for single_start",
                error_code="bad_request",
            )

        async def _request() -> GameServiceEnvelope:
            return await self._game_client.single_start(
                SingleStartRequest(
                    chat_id=command.chat_id,
                    actor_telegram_id=command.actor_telegram_id,
                    actor_username=command.actor_username,
                    actor_first_name=command.actor_first_name,
                    bet=self._resolve_bet(command.bet),
                )
            )

        envelope = await self._execute_with_auto_register(command=command, request=_request)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_single_stop(self, command: RouterCommand) -> RouterResult:
        if command.actor_telegram_id is None:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for single_stop",
                error_code="bad_request",
            )

        async def _request() -> GameServiceEnvelope:
            return await self._game_client.single_stop(
                SingleStopRequest(
                    chat_id=command.chat_id,
                    actor_telegram_id=command.actor_telegram_id,
                    actor_username=command.actor_username,
                    actor_first_name=command.actor_first_name,
                )
            )

        envelope = await self._execute_with_auto_register(command=command, request=_request)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_player_register(self, command: RouterCommand) -> RouterResult:
        if command.actor_telegram_id is None:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for player_register",
                error_code="bad_request",
            )

        envelope = await self._game_client.register_player(
            RegisterPlayerRequest(
                telegram_id=command.actor_telegram_id,
                username=command.actor_username,
                first_name=command.actor_first_name,
                bank=self._resolve_register_bank(command.bet),
            )
        )
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_player_action(self, command: RouterCommand) -> RouterResult:
        if command.actor_telegram_id is None:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for player_action",
                error_code="bad_request",
            )

        if command.action is None:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="action is required for player_action",
                error_code="bad_request",
            )

        if command.turn_version is None:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="turn_version is required for player_action",
                error_code="bad_request",
            )

        stale_guard = await self._check_stale_before_action(command)
        if stale_guard is not None:
            return stale_guard

        async def _request() -> GameServiceEnvelope:
            return await self._game_client.player_action(
                PlayerActionRequest(
                    chat_id=command.chat_id,
                    chat_type=command.chat_type,
                    actor_telegram_id=command.actor_telegram_id,
                    actor_username=command.actor_username,
                    actor_first_name=command.actor_first_name,
                    action=command.action,
                    turn_version=command.turn_version,
                )
            )

        envelope = await self._execute_with_auto_register(command=command, request=_request)

        if (
            envelope.error is not None
            and envelope.error.code == GameErrorCode.STALE_TURN
        ):
            await self._refresh_context(command)
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="stale_turn: local context refreshed",
                error_code=GameErrorCode.STALE_TURN.value,
                data=envelope.data,
            )

        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_current_session(self, command: RouterCommand) -> RouterResult:
        envelope = await self._game_client.current_session(
            CurrentSessionRequest(
                chat_id=command.chat_id,
                chat_type=command.chat_type,
            )
        )
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_admin_topup(self, command: RouterCommand) -> RouterResult:
        auth_error = self._validate_admin_auth(command)
        if auth_error is not None:
            return auth_error

        if not command.admin_target_username:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="username is required for admin_topup",
                error_code="bad_request",
            )

        if command.bet is None or command.bet <= 0:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="positive amount is required for admin_topup",
                error_code="bad_request",
            )

        envelope = await self._game_client.admin_topup(
            AdminTopupRequest(
                username=command.admin_target_username,
                amount=command.bet,
            )
        )
        return self._to_result(command=command, envelope=envelope)

    async def handle_admin_ban(self, command: RouterCommand) -> RouterResult:
        auth_error = self._validate_admin_auth(command)
        if auth_error is not None:
            return auth_error

        if not command.admin_target_username:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="username is required for admin_ban",
                error_code="bad_request",
            )

        envelope = await self._game_client.admin_ban(
            AdminBanRequest(username=command.admin_target_username)
        )
        return self._to_result(command=command, envelope=envelope)

    @staticmethod
    def _validate_admin_auth(command: RouterCommand) -> RouterResult | None:
        if command.chat_type != "single":
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="Admin commands are available only in private chat",
                error_code="authorization_error",
            )

        if command.actor_telegram_id != ADMIN_TELEGRAM_ID:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="Only admin can run this command",
                error_code="authorization_error",
            )

        return None

    @staticmethod
    def _resolve_bet(bet: int | None) -> int:
        return bet if bet is not None else DEFAULT_BET

    @staticmethod
    def _resolve_register_bank(bank: int | None) -> int:
        return bank if bank is not None else DEFAULT_REGISTER_BANK

    async def _execute_with_auto_register(
        self,
        *,
        command: RouterCommand,
        request: Callable[[], Awaitable[GameServiceEnvelope]],
    ) -> GameServiceEnvelope:
        envelope = await request()
        if not self._should_auto_register(command=command, envelope=envelope):
            return envelope

        register_envelope = await self._game_client.register_player(
            RegisterPlayerRequest(
                telegram_id=command.actor_telegram_id,
                username=command.actor_username,
                first_name=command.actor_first_name,
                bank=DEFAULT_REGISTER_BANK,
            )
        )

        if (
            not register_envelope.success
            and (
                register_envelope.error is None
                or register_envelope.error.code != GameErrorCode.STATE_CONFLICT
            )
        ):
            return register_envelope

        return await request()

    @staticmethod
    def _should_auto_register(
        *,
        command: RouterCommand,
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

    async def _check_stale_before_action(self, command: RouterCommand) -> RouterResult | None:
        if self._session_context_store is None:
            return None

        context = await self._session_context_store.get(command.chat_id)
        if context is None or context.turn_version is None:
            return None

        if command.turn_version == context.turn_version:
            return None

        return RouterResult(
            success=False,
            command_type=command.command_type,
            message=(
                "stale_turn: local guard blocked action "
                f"command_turn={command.turn_version} context_turn={context.turn_version}"
            ),
            error_code=GameErrorCode.STALE_TURN.value,
        )

    async def _refresh_context(self, command: RouterCommand) -> None:
        if self._session_context_store is None:
            return

        envelope = await self._game_client.current_session(
            CurrentSessionRequest(
                chat_id=command.chat_id,
                chat_type=command.chat_type,
            )
        )
        await self._update_context_from_envelope(command=command, envelope=envelope)

    async def _update_context_from_envelope(
        self,
        *,
        command: RouterCommand,
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
        command: RouterCommand,
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

        current_timer_raw = data.get("current_timer")
        current_timer = str(current_timer_raw) if current_timer_raw is not None else None

        return SessionContext(
            chat_id=command.chat_id,
            chat_type=command.chat_type,
            session_id=session_id,
            turn_version=turn_version,
            current_timer=current_timer,
            current_player_telegram_id=current_player_telegram_id,
            available_moves=available_moves,
        )

    @staticmethod
    def _to_result(command: RouterCommand, envelope: object) -> RouterResult:
        if not isinstance(envelope, GameServiceEnvelope):
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message="Invalid game-service response",
                error_code="transport_error",
            )

        if envelope.success:
            return RouterResult(
                success=True,
                command_type=command.command_type,
                message="ok",
                data=envelope.data,
            )

        error_message = envelope.error.message if envelope.error is not None else "game call failed"
        error_code = envelope.error.code.value if envelope.error is not None else "unknown"
        return RouterResult(
            success=False,
            command_type=command.command_type,
            message=error_message,
            error_code=error_code,
            data=envelope.data,
        )
