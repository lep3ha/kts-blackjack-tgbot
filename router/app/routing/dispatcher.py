from typing import Awaitable
from typing import Callable

from app.routing.models import CommandType
from app.routing.models import RouterCommand
from app.routing.models import RouterResult


CommandHandler = Callable[[RouterCommand], Awaitable[RouterResult]]


class RouterCommandDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[CommandType, CommandHandler] = {}

    def register(self, command_type: CommandType, handler: CommandHandler) -> None:
        self._handlers[command_type] = handler

    async def dispatch(self, command: RouterCommand) -> RouterResult:
        handler = self._handlers.get(command.command_type)
        if handler is None:
            return RouterResult(
                success=False,
                command_type=command.command_type,
                message=f"No handler for command_type={command.command_type}",
                error_code="unsupported_command",
            )

        return await handler(command)
