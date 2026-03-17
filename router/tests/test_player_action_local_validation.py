import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.game_client.models import GameServiceEnvelope
from app.routing.handlers import GameCommandHandlers
from app.routing.models import RouterCommand
from app.state.models import SessionContext


def _make_player_action_command() -> RouterCommand:
    return RouterCommand(
        update_id=1,
        chat_id="42",
        chat_type="single",
        actor_telegram_id="100",
        actor_username="u",
        actor_first_name="U",
        command_type="player_action",
        action="hit",
        turn_version=7,
    )


def test_player_action_rejected_when_not_current_player():
    client = SimpleNamespace(
        player_action=AsyncMock(),
        register_player=AsyncMock(),
        current_session=AsyncMock(),
    )
    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(
        chat_id="42",
        chat_type="single",
        turn_version=7,
        current_player_telegram_id="999",
        available_moves=["hit", "stand"],
    )
    handlers = GameCommandHandlers(client, session_context_store=context_store)

    result = asyncio.run(handlers.handle_player_action(_make_player_action_command()))

    assert result.success is False
    assert result.error_code == "not_your_turn"
    client.player_action.assert_not_awaited()


def test_player_action_rejected_when_move_not_available():
    client = SimpleNamespace(
        player_action=AsyncMock(),
        register_player=AsyncMock(),
        current_session=AsyncMock(),
    )
    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(
        chat_id="42",
        chat_type="single",
        turn_version=7,
        current_player_telegram_id="100",
        available_moves=["stand"],
    )
    handlers = GameCommandHandlers(client, session_context_store=context_store)

    result = asyncio.run(handlers.handle_player_action(_make_player_action_command()))

    assert result.success is False
    assert result.error_code == "invalid_local_action"
    client.player_action.assert_not_awaited()


def test_player_action_calls_api_when_local_checks_pass():
    client = SimpleNamespace(
        player_action=AsyncMock(
            return_value=GameServiceEnvelope(
                success=True,
                data={"session_id": 1, "turn_version": 8},
                error=None,
            )
        ),
        register_player=AsyncMock(),
        current_session=AsyncMock(),
    )
    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(
        chat_id="42",
        chat_type="single",
        turn_version=7,
        current_player_telegram_id="100",
        available_moves=["hit", "stand"],
    )
    handlers = GameCommandHandlers(client, session_context_store=context_store)

    result = asyncio.run(handlers.handle_player_action(_make_player_action_command()))

    assert result.success is True
    client.player_action.assert_awaited_once()
