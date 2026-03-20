import asyncio
from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.routing.game_client.models import GameErrorCode
from app.routing.game_client.models import GameServiceEnvelope
from app.routing.game_client.models import GameServiceError
from app.routing.game_client.models import TimeoutTurnRequest
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


def test_timeout_executor_notice_includes_second_hand_suffix_after_split():
    game_client = AsyncMock()
    game_client.timeout_turn.return_value = GameServiceEnvelope(
        success=True,
        data={
            "chat_mode": "single",
            "runtime_state": "player_turn",
            "dealer": {"cards": ["A♠", "?"], "is_final": False, "is_revealed": False},
            "participants": [{"telegram_id": "tg-1", "username": "alice", "cards": ["8H", "8D"]}],
            "current_player": {
                "telegram_id": "tg-1",
                "username": "alice",
                "participant_status": "active",
                "hand_index": 1,
            },
            "available_moves": ["stand"],
            "turn_version": 11,
        },
    )

    sender = AsyncMock()

    executor = GameServiceTimeoutExecutor(game_client, sender)
    asyncio.run(executor.execute_timeout(_make_task()))

    sender.send_text.assert_awaited_once()
    text = sender.send_text.await_args.kwargs["text"]
    assert "Время вышло" in text
    assert "Рука 2" in text


def test_timeout_turn_request_supports_hand_index_for_split_context() -> None:
    request = TimeoutTurnRequest(
        chat_id="chat-1",
        chat_type="single",
        turn_version=10,
        hand_index=1,
    )
    assert request.hand_index == 1


def test_timeout_executor_propagates_hand_index_to_game_service_timeout_call():
    game_client = AsyncMock()
    game_client.timeout_turn.return_value = GameServiceEnvelope(success=True, data={"current_player": None})

    sender = AsyncMock()

    executor = GameServiceTimeoutExecutor(game_client, sender)
    task = SimpleNamespace(
        chat_id="chat-1",
        chat_type="single",
        session_id=1,
        turn_version=10,
        hand_index=1,
        due_at=datetime.now(timezone.utc),
    )

    asyncio.run(executor.execute_timeout(task))

    sent_request = game_client.timeout_turn.await_args.args[0]
    assert sent_request.hand_index == 1
