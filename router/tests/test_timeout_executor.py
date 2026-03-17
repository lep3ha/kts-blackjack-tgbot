import asyncio
from datetime import datetime
from datetime import timezone
from unittest.mock import AsyncMock

from app.game_client.models import GameErrorCode
from app.game_client.models import GameServiceEnvelope
from app.game_client.models import GameServiceError
from app.timers.executor import GameServiceTimeoutExecutor
from app.timers.models import TimeoutTask


def _make_task() -> TimeoutTask:
    return TimeoutTask(
        chat_id="chat-1",
        chat_type="single",
        session_id=1,
        turn_version=10,
        due_at=datetime.now(timezone.utc),
    )


def test_timeout_executor_sends_notice_when_timeout_applied():
    game_client = AsyncMock()
    game_client.timeout_turn.return_value = GameServiceEnvelope(
        success=True,
        data={
            "chat_mode": "single",
            "runtime_state": "turn",
            "dealer": {"cards": ["A♠", "?"]},
            "participants": [{"telegram_id": "tg-1", "username": "alice"}],
            "current_player": {
                "telegram_id": "tg-2",
                "username": "bob",
                "participant_status": "waiting",
            },
        },
    )

    sender = AsyncMock()

    executor = GameServiceTimeoutExecutor(game_client, sender)
    asyncio.run(executor.execute_timeout(_make_task()))

    sender.send_text.assert_awaited_once()
    kwargs = sender.send_text.await_args.kwargs
    assert kwargs["chat_id"] == "chat-1"
    assert "Время вышло" in kwargs["text"]


def test_timeout_executor_skips_notice_for_noop_when_player_already_acted():
    game_client = AsyncMock()
    game_client.timeout_turn.return_value = GameServiceEnvelope(
        success=True,
        data={
            "current_player": {
                "telegram_id": "tg-1",
                "username": "alice",
                "participant_status": "inactive",
            }
        },
    )

    sender = AsyncMock()

    executor = GameServiceTimeoutExecutor(game_client, sender)
    asyncio.run(executor.execute_timeout(_make_task()))

    sender.send_text.assert_not_awaited()


def test_timeout_executor_skips_notice_on_stale_turn_error():
    game_client = AsyncMock()
    game_client.timeout_turn.return_value = GameServiceEnvelope(
        success=False,
        error=GameServiceError(
            code=GameErrorCode.STALE_TURN,
            message="stale turn version",
        ),
        data={"session_id": 1},
    )

    sender = AsyncMock()

    executor = GameServiceTimeoutExecutor(game_client, sender)
    asyncio.run(executor.execute_timeout(_make_task()))

    sender.send_text.assert_not_awaited()
