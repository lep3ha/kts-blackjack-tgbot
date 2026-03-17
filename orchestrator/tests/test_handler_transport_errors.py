import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.routing.handlers import GameCommandHandlers
from app.routing.models import OrchestratorCommand


def _make_command(command_type: str) -> OrchestratorCommand:
    return OrchestratorCommand(
        update_id=1,
        chat_id="42",
        chat_type="single",
        actor_telegram_id="100",
        actor_username="user",
        actor_first_name="User",
        command_type=command_type,
        action="hit" if command_type == "player_action" else None,
        turn_version=5 if command_type == "player_action" else None,
    )


def test_current_session_transport_error_returns_transport_code():
    client = SimpleNamespace(
        current_session=AsyncMock(side_effect=RuntimeError("upstream down")),
    )
    handlers = GameCommandHandlers(client)

    result = asyncio.run(handlers.handle_current_session(_make_command("current_session")))

    assert result.success is False
    assert result.error_code == "transport_error"


def test_player_register_transport_error_returns_transport_code():
    client = SimpleNamespace(
        register_player=AsyncMock(side_effect=RuntimeError("upstream down")),
    )
    handlers = GameCommandHandlers(client)

    result = asyncio.run(handlers.handle_player_register(_make_command("player_register")))

    assert result.success is False
    assert result.error_code == "transport_error"


def test_player_action_transport_error_returns_transport_code():
    client = SimpleNamespace(
        player_action=AsyncMock(side_effect=RuntimeError("upstream down")),
        register_player=AsyncMock(),
        current_session=AsyncMock(),
    )
    handlers = GameCommandHandlers(client)

    result = asyncio.run(handlers.handle_player_action(_make_command("player_action")))

    assert result.success is False
    assert result.error_code == "transport_error"
