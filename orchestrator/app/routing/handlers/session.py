from typing import cast

from app.routing.game_client.models import CurrentSessionRequest
from app.routing.game_client.models import GameErrorCode
from app.routing.game_client.models import GameServiceEnvelope
from app.routing.game_client.models import GroupJoinRequest
from app.routing.game_client.models import GroupOpenRequest
from app.routing.game_client.models import GroupPlayerStopRequest
from app.routing.game_client.models import GroupStartRequest
from app.routing.game_client.models import PlayerActionRequest
from app.routing.game_client.models import PlayerBalanceRequest
from app.routing.game_client.models import RegisterPlayerRequest
from app.routing.game_client.models import SingleStartRequest
from app.routing.game_client.models import SingleStopRequest
from app.routing.models import OrchestratorCommand
from app.routing.models import OrchestratorResult

from .base import BaseCommandHandlers


class SessionCommandHandlers(BaseCommandHandlers):
    async def handle_tutorial(self, command: OrchestratorCommand) -> OrchestratorResult:
        return OrchestratorResult(
            success=True,
            command_type=command.command_type,
            message="ok",
            data={"chat_type": command.chat_type},
        )

    async def handle_group_open(self, command: OrchestratorCommand) -> OrchestratorResult:
        if command.actor_telegram_id is None:
            return OrchestratorResult(
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

        envelope_or_error = await self._execute_with_auto_register(command=command, request=_request)
        if isinstance(envelope_or_error, OrchestratorResult):
            return envelope_or_error
        envelope = cast(GameServiceEnvelope, envelope_or_error)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_group_start(self, command: OrchestratorCommand) -> OrchestratorResult:
        if command.actor_telegram_id is None:
            return OrchestratorResult(
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

        envelope_or_error = await self._execute_with_auto_register(command=command, request=_request)
        if isinstance(envelope_or_error, OrchestratorResult):
            return envelope_or_error
        envelope = cast(GameServiceEnvelope, envelope_or_error)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_group_join(self, command: OrchestratorCommand) -> OrchestratorResult:
        if command.actor_telegram_id is None:
            return OrchestratorResult(
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

        envelope_or_error = await self._execute_with_auto_register(command=command, request=_request)
        if isinstance(envelope_or_error, OrchestratorResult):
            return envelope_or_error
        envelope = cast(GameServiceEnvelope, envelope_or_error)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_group_stop(self, command: OrchestratorCommand) -> OrchestratorResult:
        if command.actor_telegram_id is None:
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for group_stop",
                error_code="bad_request",
            )

        async def _request() -> GameServiceEnvelope:
            return await self._game_client.group_player_stop(
                GroupPlayerStopRequest(
                    chat_id=command.chat_id,
                    actor_telegram_id=command.actor_telegram_id,
                    actor_username=command.actor_username,
                    actor_first_name=command.actor_first_name,
                )
            )

        envelope_or_error = await self._execute_with_auto_register(command=command, request=_request)
        if isinstance(envelope_or_error, OrchestratorResult):
            return envelope_or_error
        envelope = cast(GameServiceEnvelope, envelope_or_error)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_single_start(self, command: OrchestratorCommand) -> OrchestratorResult:
        if command.actor_telegram_id is None:
            return OrchestratorResult(
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

        envelope_or_error = await self._execute_with_auto_register(command=command, request=_request)
        if isinstance(envelope_or_error, OrchestratorResult):
            return envelope_or_error
        envelope = cast(GameServiceEnvelope, envelope_or_error)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_single_stop(self, command: OrchestratorCommand) -> OrchestratorResult:
        if command.actor_telegram_id is None:
            return OrchestratorResult(
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

        envelope_or_error = await self._execute_with_auto_register(command=command, request=_request)
        if isinstance(envelope_or_error, OrchestratorResult):
            return envelope_or_error
        envelope = cast(GameServiceEnvelope, envelope_or_error)
        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_player_register(self, command: OrchestratorCommand) -> OrchestratorResult:
        if command.actor_telegram_id is None:
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for player_register",
                error_code="bad_request",
            )

        try:
            envelope = await self._game_client.register_player(
                RegisterPlayerRequest(
                    telegram_id=command.actor_telegram_id,
                    username=command.actor_username,
                    first_name=command.actor_first_name,
                    bank=self._resolve_register_bank(command.bet),
                )
            )
        except Exception:
            return self._request_failed_result(command)

        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_player_balance(self, command: OrchestratorCommand) -> OrchestratorResult:
        if command.actor_telegram_id is None:
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for player_balance",
                error_code="bad_request",
            )

        try:
            envelope = await self._game_client.player_balance(
                PlayerBalanceRequest(telegram_id=command.actor_telegram_id)
            )
        except Exception:
            return self._request_failed_result(command)

        return self._to_result(command=command, envelope=envelope)

    async def handle_player_action(self, command: OrchestratorCommand) -> OrchestratorResult:
        if command.actor_telegram_id is None:
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="actor_telegram_id is required for player_action",
                error_code="bad_request",
            )

        if command.action is None:
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="action is required for player_action",
                error_code="bad_request",
            )

        if command.turn_version is None:
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="turn_version is required for player_action",
                error_code="bad_request",
            )

        local_guard_result = await self._check_stale_before_action(command)
        if local_guard_result is not None:
            return local_guard_result

        local_guard_result = await self._check_turn_owner_before_action(command)
        if local_guard_result is not None:
            return local_guard_result

        local_guard_result = await self._check_available_moves_before_action(command)
        if local_guard_result is not None:
            return local_guard_result

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
                    hand_index=command.hand_index,
                )
            )

        envelope_or_error = await self._execute_with_auto_register(command=command, request=_request)
        if isinstance(envelope_or_error, OrchestratorResult):
            return envelope_or_error
        envelope = cast(GameServiceEnvelope, envelope_or_error)

        if envelope.error is not None and envelope.error.code == GameErrorCode.STALE_TURN:
            await self._refresh_context(command)
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="stale_turn: local context refreshed",
                error_code=GameErrorCode.STALE_TURN.value,
                data=envelope.data,
            )

        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)

    async def handle_current_session(self, command: OrchestratorCommand) -> OrchestratorResult:
        try:
            envelope = await self._game_client.current_session(
                CurrentSessionRequest(
                    chat_id=command.chat_id,
                    chat_type=command.chat_type,
                )
            )
        except Exception:
            return self._request_failed_result(command)

        await self._update_context_from_envelope(command=command, envelope=envelope)
        return self._to_result(command=command, envelope=envelope)
