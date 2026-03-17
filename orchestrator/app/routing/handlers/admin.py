from app.routing.game_client.models import AdminBanRequest
from app.routing.game_client.models import AdminTopupRequest
from app.routing.models import OrchestratorCommand
from app.routing.models import OrchestratorResult

from .base import BaseCommandHandlers
from .constants import ADMIN_TELEGRAM_ID


class AdminCommandHandlers(BaseCommandHandlers):
    async def handle_admin_topup(self, command: OrchestratorCommand) -> OrchestratorResult:
        auth_error = self._validate_admin_auth(command)
        if auth_error is not None:
            return auth_error

        if not command.admin_target_username:
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="username is required for admin_topup",
                error_code="bad_request",
            )

        if command.bet is None or command.bet <= 0:
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="positive amount is required for admin_topup",
                error_code="bad_request",
            )

        try:
            envelope = await self._game_client.admin_topup(
                AdminTopupRequest(
                    username=command.admin_target_username,
                    amount=command.bet,
                )
            )
        except Exception:
            return self._request_failed_result(command)

        return self._to_result(command=command, envelope=envelope)

    async def handle_admin_ban(self, command: OrchestratorCommand) -> OrchestratorResult:
        auth_error = self._validate_admin_auth(command)
        if auth_error is not None:
            return auth_error

        if not command.admin_target_username:
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="username is required for admin_ban",
                error_code="bad_request",
            )

        try:
            envelope = await self._game_client.admin_ban(
                AdminBanRequest(username=command.admin_target_username)
            )
        except Exception:
            return self._request_failed_result(command)

        return self._to_result(command=command, envelope=envelope)

    @staticmethod
    def _validate_admin_auth(command: OrchestratorCommand) -> OrchestratorResult | None:
        if command.chat_type != "single":
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="Admin commands are available only in private chat",
                error_code="authorization_error",
            )

        if command.actor_telegram_id != ADMIN_TELEGRAM_ID:
            return OrchestratorResult(
                success=False,
                command_type=command.command_type,
                message="Only admin can run this command",
                error_code="authorization_error",
            )

        return None
