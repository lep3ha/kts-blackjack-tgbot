import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.routing.game_client.models import GameErrorCode
from app.routing.game_client.models import GameServiceEnvelope
from app.routing.game_client.models import GameServiceError
from app.routing.handlers import ADMIN_TELEGRAM_ID
from app.routing.handlers import GameCommandHandlers
from app.routing.models import OrchestratorCommand


def _make_command(
    *,
    command_type: str,
    chat_type: str = "single",
    actor_telegram_id: str | None = ADMIN_TELEGRAM_ID,
    username: str | None = "target_user",
    amount: int | None = 500,
) -> OrchestratorCommand:
    return OrchestratorCommand(
        update_id=1,
        chat_id="42",
        chat_type=chat_type,
        actor_telegram_id=actor_telegram_id,
        actor_username="admin",
        actor_first_name="Admin",
        command_type=command_type,
        admin_target_username=username,
        bet=amount,
    )


def _success_envelope(data: dict) -> GameServiceEnvelope:
    return GameServiceEnvelope(success=True, data=data)


def _error_envelope(code: GameErrorCode, message: str) -> GameServiceEnvelope:
    return GameServiceEnvelope(success=False, error=GameServiceError(code=code, message=message))


def test_admin_topup_unauthorized_actor():
    client = SimpleNamespace(admin_topup=AsyncMock())
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="admin_topup", actor_telegram_id="123")

    result = asyncio.run(handlers.handle_admin_topup(command))

    assert result.success is False
    assert result.error_code == "authorization_error"
    client.admin_topup.assert_not_awaited()


def test_admin_topup_rejected_in_group_chat():
    client = SimpleNamespace(admin_topup=AsyncMock())
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="admin_topup", chat_type="group")

    result = asyncio.run(handlers.handle_admin_topup(command))

    assert result.success is False
    assert result.error_code == "authorization_error"
    client.admin_topup.assert_not_awaited()


def test_admin_topup_requires_username():
    client = SimpleNamespace(admin_topup=AsyncMock())
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="admin_topup", username=None)

    result = asyncio.run(handlers.handle_admin_topup(command))

    assert result.success is False
    assert result.error_code == "bad_request"
    client.admin_topup.assert_not_awaited()


def test_admin_topup_requires_positive_amount():
    client = SimpleNamespace(admin_topup=AsyncMock())
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="admin_topup", amount=0)

    result = asyncio.run(handlers.handle_admin_topup(command))

    assert result.success is False
    assert result.error_code == "bad_request"
    client.admin_topup.assert_not_awaited()


def test_admin_topup_happy_path():
    client = SimpleNamespace(
        admin_topup=AsyncMock(
            return_value=_success_envelope({"username": "target_user", "new_bank": 1500})
        )
    )
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="admin_topup", username="target_user", amount=500)

    result = asyncio.run(handlers.handle_admin_topup(command))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data.get("new_bank") == 1500
    client.admin_topup.assert_awaited_once()


def test_admin_ban_unauthorized_actor():
    client = SimpleNamespace(admin_ban=AsyncMock())
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="admin_ban", actor_telegram_id="123")

    result = asyncio.run(handlers.handle_admin_ban(command))

    assert result.success is False
    assert result.error_code == "authorization_error"
    client.admin_ban.assert_not_awaited()


def test_admin_ban_happy_path():
    client = SimpleNamespace(
        admin_ban=AsyncMock(return_value=_success_envelope({"username": "target_user", "is_banned": True}))
    )
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="admin_ban", username="target_user", amount=None)

    result = asyncio.run(handlers.handle_admin_ban(command))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data.get("is_banned") is True
    client.admin_ban.assert_awaited_once()


def test_admin_ban_game_error_propagates():
    client = SimpleNamespace(
        admin_ban=AsyncMock(
            return_value=_error_envelope(GameErrorCode.NOT_FOUND, "Player with username 'ghost' not found")
        )
    )
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="admin_ban", username="ghost", amount=None)

    result = asyncio.run(handlers.handle_admin_ban(command))

    assert result.success is False
    assert result.error_code == "not_found"


def test_admin_topup_transport_error_returns_user_friendly_error_code():
    client = SimpleNamespace(
        admin_topup=AsyncMock(side_effect=RuntimeError("connection reset"))
    )
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="admin_topup", username="target_user", amount=500)

    result = asyncio.run(handlers.handle_admin_topup(command))

    assert result.success is False
    assert result.error_code == "transport_error"


def test_admin_ban_transport_error_returns_user_friendly_error_code():
    client = SimpleNamespace(
        admin_ban=AsyncMock(side_effect=RuntimeError("connection reset"))
    )
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="admin_ban", username="target_user", amount=None)

    result = asyncio.run(handlers.handle_admin_ban(command))

    assert result.success is False
    assert result.error_code == "transport_error"


def test_tutorial_handler_returns_success_without_game_call():
    client = SimpleNamespace()
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="tutorial", amount=None)

    result = asyncio.run(handlers.handle_tutorial(command))

    assert result.success is True
    assert result.command_type == "tutorial"
    assert isinstance(result.data, dict)
    assert result.data.get("chat_type") == "single"


def test_group_stop_handler_requires_actor_telegram_id():
    client = SimpleNamespace(group_player_stop=AsyncMock())
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="group_stop", chat_type="group", actor_telegram_id=None, amount=None)

    result = asyncio.run(handlers.handle_group_stop(command))

    assert result.success is False
    assert result.error_code == "bad_request"
    client.group_player_stop.assert_not_awaited()


def test_group_stop_handler_calls_group_player_stop():
    client = SimpleNamespace(
        group_player_stop=AsyncMock(return_value=_success_envelope({"session_status": "in_progress"})),
        register_player=AsyncMock(),
        current_session=AsyncMock(),
    )
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="group_stop", chat_type="group", amount=None)

    result = asyncio.run(handlers.handle_group_stop(command))

    assert result.success is True
    client.group_player_stop.assert_awaited_once()


def test_player_balance_handler_returns_bank_for_actor():
    client = SimpleNamespace(
        player_balance=AsyncMock(
            return_value=_success_envelope(
                {
                    "id": 1,
                    "telegram_id": "42",
                    "username": "alice",
                    "bank": 1337,
                }
            )
        )
    )
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="player_balance", actor_telegram_id="42", amount=None)

    result = asyncio.run(handlers.handle_player_balance(command))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data.get("bank") == 1337
    client.player_balance.assert_awaited_once()


def test_player_balance_handler_requires_actor_telegram_id():
    client = SimpleNamespace(player_balance=AsyncMock())
    handlers = GameCommandHandlers(client)
    command = _make_command(command_type="player_balance", actor_telegram_id=None, amount=None)

    result = asyncio.run(handlers.handle_player_balance(command))

    assert result.success is False
    assert result.error_code == "bad_request"
    client.player_balance.assert_not_awaited()
