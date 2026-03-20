from datetime import datetime
from datetime import timezone

from app.routing.normalizer import TelegramUpdateNormalizer
from app.sender.presenter import _build_action_inline_keyboard
from app.upstream.models import TelegramUpdateEnvelope


normalizer = TelegramUpdateNormalizer()


def _make_message_envelope(text: str) -> TelegramUpdateEnvelope:
    return TelegramUpdateEnvelope(
        update_id=1,
        update_type="message",
        source_key="chat:42",
        partition_key="chat:42",
        next_offset=2,
        received_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        payload={
            "message": {
                "text": text,
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 7, "username": "u", "first_name": "F"},
            }
        },
    )


def _make_callback_envelope(callback_data: str) -> TelegramUpdateEnvelope:
    return TelegramUpdateEnvelope(
        update_id=1,
        update_type="callback_query",
        source_key="chat:42",
        partition_key="chat:42",
        next_offset=2,
        received_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        payload={
            "callback_query": {
                "id": "cb-1",
                "from": {"id": 7, "username": "u", "first_name": "F"},
                "message": {
                    "message_id": 10,
                    "chat": {"id": 42, "type": "private"},
                    "text": "state",
                },
                "data": callback_data,
            }
        },
    )


def test_split_slash_command_is_supported() -> None:
    cmd = normalizer.normalize(_make_message_envelope("/split"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "split"


def test_split_callback_is_supported() -> None:
    cmd = normalizer.normalize(_make_callback_envelope("action:split:tv:1"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "split"
    assert cmd.turn_version == 1


def test_action_inline_keyboard_renders_split_when_provided() -> None:
    kb = _build_action_inline_keyboard({"available_moves": ["hit", "stand", "double", "split"], "turn_version": 1})
    assert kb is not None
    actions = {button.action for row in kb.rows for button in row}
    assert "action:split:tv:1" in actions
