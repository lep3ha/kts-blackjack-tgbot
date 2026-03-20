"""Tests for Phase 3: delete-before / save-after message_id in OrchestratorPipeline."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routing.normalizer import TelegramUpdateNormalizer
from app.routing.models import OrchestratorCommand, OrchestratorResult
from app.routing.pipeline import OrchestratorPipeline
from app.state.models import SessionContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_command(command_type: str = "player_action") -> OrchestratorCommand:
    return OrchestratorCommand(
        update_id=1,
        chat_id="chat-1",
        chat_type="single",
        actor_telegram_id="tg-1",
        actor_username=None,
        actor_first_name=None,
        command_type=command_type,
        action="hit" if command_type == "player_action" else None,
        turn_version=2 if command_type == "player_action" else None,
        bet=None,
    )


def _make_result(command_type: str = "player_action") -> OrchestratorResult:
    return OrchestratorResult(
        success=True,
        command_type=command_type,
        message="ok",
        data={"session_id": 42, "turn_version": 3, "chat_mode": "single"},
    )


def _make_context(last_bot_message_id: int | None = None) -> SessionContext:
    return SessionContext(
        chat_id="chat-1",
        chat_type="single",
        session_id=42,
        current_player_telegram_id="tg-1",
        last_bot_message_id=last_bot_message_id,
    )


def _make_pipeline(
    *,
    context: SessionContext | None = None,
    send_returns: int | None = 99,
    command_type: str = "player_action",
) -> tuple[OrchestratorPipeline, MagicMock, MagicMock, MagicMock]:
    normalizer = MagicMock()
    normalizer.normalize.return_value = _make_command(command_type)

    processor = AsyncMock()
    processor.process.return_value = _make_result(command_type)

    sender = AsyncMock()
    sender.send_text.return_value = send_returns
    sender.delete_message.return_value = None

    context_store = AsyncMock()
    context_store.get.return_value = context
    context_store.set.return_value = None

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=AsyncMock(),
        session_context_store=context_store,
        context_ttl_seconds=600,
    )
    return pipeline, sender, context_store, normalizer


def _make_envelope() -> MagicMock:
    return MagicMock()


def _make_envelope_with_chat(chat_id: str = "chat-1", text: str = "Hit") -> MagicMock:
    envelope = MagicMock()
    envelope.update_id = 1
    envelope.update_type = "message"
    envelope.source_key = chat_id
    envelope.partition_key = chat_id
    envelope.next_offset = 2
    envelope.payload = {
        "message": {
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": "tg-1"},
            "text": text,
        }
    }
    return envelope


def _make_callback_envelope_with_chat(chat_id: str = "42", callback_data: str = "action:split:tv:5:hand:1") -> MagicMock:
    envelope = MagicMock()
    envelope.update_id = 1
    envelope.update_type = "callback_query"
    envelope.source_key = chat_id
    envelope.partition_key = chat_id
    envelope.next_offset = 2
    envelope.payload = {
        "callback_query": {
            "id": "cb-1",
            "from": {"id": "tg-1", "username": "u", "first_name": "F"},
            "message": {
                "message_id": 10,
                "chat": {"id": chat_id, "type": "private"},
                "text": "state",
            },
            "data": callback_data,
        }
    }
    return envelope


# ---------------------------------------------------------------------------
# send_text return value propagation
# ---------------------------------------------------------------------------


def test_send_text_message_id_saved_to_context():
    context = _make_context(last_bot_message_id=None)
    pipeline, sender, context_store, _ = _make_pipeline(context=context, send_returns=55)

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    context_store.set.assert_awaited_once()
    saved_context: SessionContext = context_store.set.call_args[0][1]
    assert saved_context.last_bot_message_id == 55


def test_tutorial_group_saves_group_open_hint():
    normalizer = MagicMock()
    normalizer.normalize.return_value = OrchestratorCommand(
        update_id=1,
        chat_id="chat-1",
        chat_type="group",
        actor_telegram_id="tg-1",
        actor_username=None,
        actor_first_name=None,
        command_type="tutorial",
    )

    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=True,
        command_type="tutorial",
        message="ok",
        data={"chat_type": "group"},
    )

    sender = AsyncMock()
    sender.send_text.return_value = 55
    context_store = AsyncMock()
    context_store.get.return_value = None

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=AsyncMock(),
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    saved_context: SessionContext = context_store.set.call_args[0][1]
    assert saved_context.reply_action_hint == "group_open"


def test_group_lobby_result_saves_group_start_hint():
    normalizer = MagicMock()
    normalizer.normalize.return_value = OrchestratorCommand(
        update_id=1,
        chat_id="chat-1",
        chat_type="group",
        actor_telegram_id="tg-1",
        actor_username=None,
        actor_first_name=None,
        command_type="group_open",
    )

    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=True,
        command_type="group_open",
        message="ok",
        data={"session_status": "lobby_open", "chat_mode": "group"},
    )

    sender = AsyncMock()
    sender.send_text.return_value = 77
    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(chat_id="chat-1", chat_type="group")

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=AsyncMock(),
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    saved_context: SessionContext = context_store.set.call_args[0][1]
    assert saved_context.reply_action_hint == "group_start"


def test_group_open_inline_keyboard_is_not_reply_targeted_with_username():
    normalizer = MagicMock()
    normalizer.normalize.return_value = OrchestratorCommand(
        update_id=1,
        chat_id="chat-1",
        chat_type="group",
        actor_telegram_id="tg-1",
        actor_username="alice",
        actor_first_name=None,
        command_type="group_open",
    )

    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=True,
        command_type="group_open",
        message="ok",
        data={"session_status": "lobby_open", "chat_mode": "group", "bet": 100},
    )

    sender = AsyncMock()
    sender.send_text.return_value = 88
    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(chat_id="chat-1", chat_type="group")

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=AsyncMock(),
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    send_kwargs = sender.send_text.call_args.kwargs
    assert not send_kwargs["text"].startswith("@alice ")
    assert send_kwargs["keyboard"].kind == "inline"
    assert send_kwargs["parse_mode"] is None


def test_group_open_inline_keyboard_is_not_reply_targeted_with_html_mention():
    normalizer = MagicMock()
    normalizer.normalize.return_value = OrchestratorCommand(
        update_id=1,
        chat_id="chat-1",
        chat_type="group",
        actor_telegram_id="123456",
        actor_username=None,
        actor_first_name="Alice & Bob",
        command_type="group_open",
    )

    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=True,
        command_type="group_open",
        message="ok",
        data={"session_status": "lobby_open", "chat_mode": "group", "bet": 100},
    )

    sender = AsyncMock()
    sender.send_text.return_value = 88
    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(chat_id="chat-1", chat_type="group")

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=AsyncMock(),
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    send_kwargs = sender.send_text.call_args.kwargs
    assert send_kwargs["parse_mode"] is None
    assert not send_kwargs["text"].startswith('<a href="tg://user?id=123456">Alice &amp; Bob</a> ')
    assert send_kwargs["keyboard"].kind == "inline"


def test_no_save_when_send_returns_none():
    context = _make_context()
    pipeline, sender, context_store, _ = _make_pipeline(context=context, send_returns=None)

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    context_store.set.assert_not_awaited()


def test_save_creates_context_when_missing():
    pipeline, sender, context_store, _ = _make_pipeline(context=None, send_returns=55)

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    context_store.set.assert_awaited_once()
    chat_id_arg, saved_context, ttl_arg = context_store.set.call_args[0]
    assert chat_id_arg == "chat-1"
    assert saved_context.chat_id == "chat-1"
    assert saved_context.chat_type == "single"
    assert saved_context.last_bot_message_id == 55
    assert ttl_arg == 600


# ---------------------------------------------------------------------------
# delete_message called on player_action
# ---------------------------------------------------------------------------


def test_delete_called_before_send_on_player_action():
    context = _make_context(last_bot_message_id=77)
    pipeline, sender, _, _ = _make_pipeline(context=context, command_type="player_action")

    call_order = []

    async def fake_delete(**kw):
        call_order.append("delete")

    async def fake_send(**kw):
        call_order.append("send")
        return 88

    sender.delete_message.side_effect = fake_delete
    sender.send_text.side_effect = fake_send

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    assert call_order == ["delete", "send"]


def test_delete_called_with_correct_message_id():
    context = _make_context(last_bot_message_id=123)
    pipeline, sender, _, _ = _make_pipeline(context=context, command_type="player_action")

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    sender.delete_message.assert_awaited_once_with(chat_id="chat-1", message_id=123)


def test_delete_called_on_current_session():
    context = _make_context(last_bot_message_id=123)
    pipeline, sender, _, _ = _make_pipeline(context=context, command_type="current_session")

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    sender.delete_message.assert_awaited_once_with(chat_id="chat-1", message_id=123)


def test_delete_not_called_when_no_previous_message():
    context = _make_context(last_bot_message_id=None)
    pipeline, sender, _, _ = _make_pipeline(context=context, command_type="player_action")

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    sender.delete_message.assert_not_awaited()


def test_delete_not_called_when_context_is_missing():
    pipeline, sender, _, _ = _make_pipeline(context=None, command_type="player_action")

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    sender.delete_message.assert_not_awaited()


def test_delete_not_called_for_non_player_action():
    context = _make_context(last_bot_message_id=50)
    pipeline, sender, _, _ = _make_pipeline(context=context, command_type="group_open")

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    sender.delete_message.assert_not_awaited()


def test_delete_not_called_when_player_action_failed():
    context = _make_context(last_bot_message_id=50)
    pipeline, sender, _, _ = _make_pipeline(context=context, command_type="player_action")
    pipeline._processor.process.return_value = OrchestratorResult(
        success=False,
        command_type="player_action",
        message="not_your_turn",
        error_code="not_your_turn",
    )

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    sender.delete_message.assert_not_awaited()


def test_delete_not_called_when_player_action_from_non_current_player():
    context = SessionContext(
        chat_id="chat-1",
        chat_type="single",
        session_id=42,
        current_player_telegram_id="someone-else",
        last_bot_message_id=50,
    )
    pipeline, sender, _, _ = _make_pipeline(context=context, command_type="player_action")

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    sender.delete_message.assert_not_awaited()


def test_delete_not_called_when_no_context_store():
    """Pipeline with no context store should send fine without deletes."""
    normalizer = MagicMock()
    normalizer.normalize.return_value = _make_command("player_action")
    processor = AsyncMock()
    processor.process.return_value = _make_result()
    sender = AsyncMock()
    sender.send_text.return_value = 42
    sender.delete_message.return_value = None

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=AsyncMock(),
        session_context_store=None,
    )

    asyncio.run(pipeline.process_envelope(MagicMock()))

    sender.delete_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# Fail-safe: errors during delete must not crash the pipeline
# ---------------------------------------------------------------------------


def test_delete_failure_does_not_crash_pipeline():
    context = _make_context(last_bot_message_id=10)
    pipeline, sender, context_store, _ = _make_pipeline(context=context)
    sender.delete_message.side_effect = RuntimeError("Telegram timeout")

    # Should not raise
    asyncio.run(pipeline.process_envelope(_make_envelope()))

    # Message was still sent
    sender.send_text.assert_awaited_once()


def test_context_get_failure_does_not_crash_pipeline():
    context = _make_context(last_bot_message_id=10)
    pipeline, sender, context_store, _ = _make_pipeline(context=context)
    context_store.get.side_effect = RuntimeError("Redis read timeout")

    # Should not raise
    asyncio.run(pipeline.process_envelope(_make_envelope()))

    # Delete could not run because context loading failed, but pipeline still sends message.
    sender.delete_message.assert_not_awaited()
    sender.send_text.assert_awaited_once()


def test_context_lookup_uses_command_chat_id_for_delete_flow():
    context = _make_context(last_bot_message_id=111)
    pipeline, sender, context_store, _ = _make_pipeline(context=context, command_type="player_action")

    asyncio.run(pipeline.process_envelope(_make_envelope()))

    context_store.get.assert_awaited()
    first_get_call = context_store.get.await_args_list[0]
    assert first_get_call.args == ("chat-1",)


def test_save_failure_does_not_crash_pipeline():
    context = _make_context()
    pipeline, sender, context_store, _ = _make_pipeline(context=context, send_returns=7)
    context_store.set.side_effect = RuntimeError("Redis down")

    # Should not raise
    asyncio.run(pipeline.process_envelope(_make_envelope()))

    sender.send_text.assert_awaited_once()


# ---------------------------------------------------------------------------
# Timer cancel semantics for player actions
# ---------------------------------------------------------------------------


def test_cancel_timeout_called_for_successful_current_player_action():
    normalizer = MagicMock()
    normalizer.normalize.return_value = _make_command("player_action")

    processor = AsyncMock()
    processor.process.return_value = _make_result("player_action")

    sender = AsyncMock()
    sender.send_text.return_value = 77

    timer_scheduler = AsyncMock()

    context_store = AsyncMock()
    context_store.get.return_value = _make_context(last_bot_message_id=11)
    context_store.set.return_value = None

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=timer_scheduler,
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_envelope_with_chat()))

    timer_scheduler.cancel_timeout.assert_awaited_once_with(
        chat_id="chat-1",
        session_id=42,
        turn_version=2,
    )


def test_cancel_timeout_not_called_when_player_action_fails():
    normalizer = MagicMock()
    normalizer.normalize.return_value = _make_command("player_action")

    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=False,
        command_type="player_action",
        message="stale_turn",
        error_code="stale_turn",
    )

    sender = AsyncMock()
    sender.send_text.return_value = 77

    timer_scheduler = AsyncMock()

    context_store = AsyncMock()
    context_store.get.return_value = _make_context(last_bot_message_id=11)
    context_store.set.return_value = None

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=timer_scheduler,
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_envelope_with_chat()))

    timer_scheduler.cancel_timeout.assert_not_awaited()


def test_cancel_timeout_not_called_for_non_current_player():
    normalizer = MagicMock()
    normalizer.normalize.return_value = _make_command("player_action")

    processor = AsyncMock()
    processor.process.return_value = _make_result("player_action")

    sender = AsyncMock()
    sender.send_text.return_value = 77

    timer_scheduler = AsyncMock()

    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(
        chat_id="chat-1",
        chat_type="single",
        session_id=42,
        current_player_telegram_id="someone-else",
        last_bot_message_id=11,
    )
    context_store.set.return_value = None

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=timer_scheduler,
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_envelope_with_chat()))

    timer_scheduler.cancel_timeout.assert_not_awaited()


def test_cancel_timeout_failure_does_not_crash_pipeline():
    normalizer = MagicMock()
    normalizer.normalize.return_value = _make_command("player_action")

    processor = AsyncMock()
    processor.process.return_value = _make_result("player_action")

    sender = AsyncMock()
    sender.send_text.return_value = 77

    timer_scheduler = AsyncMock()
    timer_scheduler.cancel_timeout.side_effect = RuntimeError("Redis down")

    context_store = AsyncMock()
    context_store.get.return_value = _make_context(last_bot_message_id=11)
    context_store.set.return_value = None

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=timer_scheduler,
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_envelope_with_chat()))

    sender.send_text.assert_awaited_once()


def test_schedule_timeout_includes_split_hand_index_from_snapshot():
    normalizer = MagicMock()
    normalizer.normalize.return_value = _make_command("player_action")

    due_at = (datetime.now(timezone.utc) + timedelta(seconds=45)).replace(microsecond=0)
    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=True,
        command_type="player_action",
        message="ok",
        data={
            "chat_mode": "single",
            "session_id": 42,
            "turn_version": 8,
            "current_hand_index": 1,
            "current_timer": due_at.isoformat(),
        },
    )

    sender = AsyncMock()
    sender.send_text.return_value = 77

    timer_scheduler = AsyncMock()

    context_store = AsyncMock()
    context_store.get.return_value = _make_context(last_bot_message_id=11)
    context_store.set.return_value = None

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=timer_scheduler,
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_envelope_with_chat()))

    timer_scheduler.schedule_timeout.assert_awaited_once_with(
        chat_id="chat-1",
        chat_type="single",
        session_id=42,
        turn_version=8,
        hand_index=1,
        due_at=due_at,
    )


# ---------------------------------------------------------------------------
# SessionContext: last_bot_message_id field
# ---------------------------------------------------------------------------


def test_session_context_default_no_message_id():
    ctx = SessionContext(chat_id="x", chat_type="single")
    assert ctx.last_bot_message_id is None


def test_session_context_serialises_message_id():
    ctx = SessionContext(chat_id="x", chat_type="single", last_bot_message_id=999)
    payload = ctx.model_dump_json()
    restored = SessionContext.model_validate_json(payload)
    assert restored.last_bot_message_id == 999


def test_session_context_old_payload_without_field_still_valid():
    """Backwards compatibility: old Redis entries without last_bot_message_id."""
    import json
    old_payload = json.dumps({
        "chat_id": "c1",
        "chat_type": "group",
        "session_id": 5,
        "turn_version": 2,
    })
    ctx = SessionContext.model_validate_json(old_payload)
    assert ctx.last_bot_message_id is None


# ---------------------------------------------------------------------------
# Split flow end-to-end through pipeline (normalize -> render -> send)
# ---------------------------------------------------------------------------


def test_split_callback_pipeline_renders_per_hand_breakdown_and_saves_context():
    normalizer = TelegramUpdateNormalizer()
    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=True,
        command_type="player_action",
        message="ok",
        data={
            "chat_mode": "single",
            "session_id": 42,
            "session_status": "closed",
            "runtime_state": "closed",
            "turn_version": 6,
            "dealer": {"cards": ["10S", "7H"], "is_final": True, "is_revealed": True},
            "participants": [
                {
                    "telegram_id": "tg-1",
                    "username": "alice",
                    "result": "mixed",
                    "delta": 0,
                    "hand_settlements": [
                        {"hand_index": 0, "result": "win", "delta": 100},
                        {"hand_index": 1, "result": "lose", "delta": -100},
                    ],
                }
            ],
            "available_moves": [],
            "current_timer": None,
        },
    )

    sender = AsyncMock()
    sender.send_text.return_value = 501

    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(chat_id="42", chat_type="single", session_id=42)
    context_store.set.return_value = None

    timer_scheduler = AsyncMock()

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=timer_scheduler,
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_callback_envelope_with_chat()))

    sent_text = sender.send_text.await_args.kwargs["text"]
    assert "Рука 1: win (+100)" in sent_text
    assert "Рука 2: lose (-100)" in sent_text

    dispatched_command = processor.process.await_args.args[0]
    assert dispatched_command.command_type == "player_action"
    assert dispatched_command.action == "split"
    assert dispatched_command.turn_version == 5
    assert dispatched_command.hand_index == 1

    saved_context: SessionContext = context_store.set.call_args[0][1]
    assert saved_context.last_bot_message_id == 501
    assert saved_context.reply_action_hint == "single_start"


def test_split_reply_action_pipeline_uses_context_turn_and_hand_index():
    normalizer = TelegramUpdateNormalizer()
    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=True,
        command_type="player_action",
        message="ok",
        data={
            "chat_mode": "single",
            "session_id": 42,
            "session_status": "in_progress",
            "runtime_state": "player_turn",
            "turn_version": 12,
            "dealer": {"cards": ["10S", "?"], "is_final": False, "is_revealed": False},
            "participants": [{"telegram_id": "tg-1", "username": "alice", "cards": ["8D", "3D"]}],
            "current_player": {"telegram_id": "tg-1", "username": "alice", "hand_index": 1},
            "available_moves": ["hit", "stand"],
            "current_timer": None,
        },
    )

    sender = AsyncMock()
    sender.send_text.return_value = 778

    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(
        chat_id="chat-1",
        chat_type="single",
        session_id=42,
        turn_version=11,
        current_hand_index=1,
        current_player_telegram_id="tg-1",
        available_moves=["hit", "stand"],
    )
    context_store.set.return_value = None

    timer_scheduler = AsyncMock()

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=timer_scheduler,
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_envelope_with_chat(text="Hit")))

    dispatched_command = processor.process.await_args.args[0]
    assert dispatched_command.command_type == "player_action"
    assert dispatched_command.action == "hit"
    assert dispatched_command.turn_version == 11
    assert dispatched_command.hand_index == 1


def test_split_in_progress_pipeline_renders_inline_split_button_with_style():
    normalizer = TelegramUpdateNormalizer()
    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=True,
        command_type="player_action",
        message="ok",
        data={
            "chat_mode": "single",
            "session_id": 42,
            "session_status": "in_progress",
            "runtime_state": "player_turn",
            "turn_version": 8,
            "dealer": {"cards": ["10S", "?"], "is_final": False, "is_revealed": False},
            "participants": [
                {
                    "telegram_id": "tg-1",
                    "username": "alice",
                    "cards": ["8H", "8D"],
                    "hands": [
                        {
                            "hand_index": 0,
                            "cards": ["8H", "2H"],
                            "participant_status": "inactive",
                        },
                        {
                            "hand_index": 1,
                            "cards": ["8D", "3D"],
                            "participant_status": "active",
                        },
                    ],
                }
            ],
            "current_player": {"telegram_id": "tg-1", "username": "alice", "hand_index": 1},
            "available_moves": ["hit", "stand", "double", "split"],
            "current_timer": None,
        },
    )

    sender = AsyncMock()
    sender.send_text.return_value = 777

    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(chat_id="42", chat_type="single", session_id=42)
    context_store.set.return_value = None

    timer_scheduler = AsyncMock()

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=timer_scheduler,
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_callback_envelope_with_chat(callback_data="action:split:tv:8:hand:1")))

    sent_text = sender.send_text.await_args.kwargs["text"]
    assert "Рука 1" in sent_text
    assert "Рука 2" in sent_text
    assert "текущая" in sent_text

    keyboard = sender.send_text.await_args.kwargs["keyboard"]
    assert keyboard is not None
    assert keyboard.kind == "inline"

    split_buttons = [btn for row in keyboard.rows for btn in row if btn.id == "split"]
    assert len(split_buttons) == 1
    split_button = split_buttons[0]
    assert split_button.title == "Split"
    assert split_button.action == "action:split:tv:8:hand:1"
    assert split_button.style == "secondary"


def test_split_pipeline_saves_second_hand_context_and_renders_hit_button_for_hand_two():
    normalizer = TelegramUpdateNormalizer()
    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=True,
        command_type="player_action",
        message="ok",
        data={
            "chat_mode": "single",
            "session_id": 42,
            "session_status": "in_progress",
            "runtime_state": "player_turn",
            "turn_version": 9,
            "dealer": {"cards": ["10S", "?"], "is_final": False, "is_revealed": False},
            "participants": [
                {
                    "telegram_id": "tg-1",
                    "username": "alice",
                    "cards": ["8H", "8D"],
                    "hands": [
                        {
                            "hand_index": 0,
                            "cards": ["8H", "2H"],
                            "participant_status": "inactive",
                        },
                        {
                            "hand_index": 1,
                            "cards": ["8D", "3D"],
                            "participant_status": "active",
                        },
                    ],
                }
            ],
            "current_player": {"telegram_id": "tg-1", "username": "alice", "hand_index": 1},
            # Deliberately omit top-level current_hand_index to verify fallback.
            "available_moves": ["hit", "stand"],
            "current_timer": None,
        },
    )

    sender = AsyncMock()
    sender.send_text.return_value = 779

    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(chat_id="42", chat_type="single", session_id=42)
    context_store.set.return_value = None

    timer_scheduler = AsyncMock()

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=timer_scheduler,
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_callback_envelope_with_chat(callback_data="action:split:tv:8:hand:1")))

    saved_context: SessionContext = context_store.set.call_args[0][1]
    assert saved_context.current_hand_index == 1
    assert saved_context.available_moves == ["hit", "stand"]

    keyboard = sender.send_text.await_args.kwargs["keyboard"]
    assert keyboard is not None
    hit_buttons = [btn for row in keyboard.rows for btn in row if btn.id == "hit"]
    assert len(hit_buttons) == 1
    assert hit_buttons[0].action == "action:hit:tv:9:hand:1"


def test_cancel_timeout_called_for_successful_current_player_split_callback():
    normalizer = TelegramUpdateNormalizer()
    processor = AsyncMock()
    processor.process.return_value = OrchestratorResult(
        success=True,
        command_type="player_action",
        message="ok",
        data={
            "chat_mode": "single",
            "session_id": 42,
            "session_status": "in_progress",
            "runtime_state": "player_turn",
            "turn_version": 3,
            "dealer": {"cards": ["10S", "?"], "is_final": False, "is_revealed": False},
            "participants": [{"telegram_id": "tg-1", "username": "alice", "cards": ["8H", "8D"]}],
            "current_player": {"telegram_id": "tg-1", "username": "alice", "hand_index": 1},
            "available_moves": ["hit", "stand"],
            "current_timer": None,
        },
    )

    sender = AsyncMock()
    sender.send_text.return_value = 888

    context_store = AsyncMock()
    context_store.get.return_value = SessionContext(
        chat_id="42",
        chat_type="single",
        session_id=42,
        current_player_telegram_id="tg-1",
        last_bot_message_id=10,
    )
    context_store.set.return_value = None

    timer_scheduler = AsyncMock()

    pipeline = OrchestratorPipeline(
        normalizer=normalizer,
        processor=processor,
        sender=sender,
        timer_scheduler=timer_scheduler,
        session_context_store=context_store,
        context_ttl_seconds=600,
    )

    asyncio.run(pipeline.process_envelope(_make_callback_envelope_with_chat(callback_data="action:split:tv:2:hand:1")))

    timer_scheduler.cancel_timeout.assert_awaited_once_with(
        chat_id="42",
        session_id=42,
        turn_version=2,
    )
