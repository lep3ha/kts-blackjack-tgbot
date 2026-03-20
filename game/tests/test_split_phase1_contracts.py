import pytest
from pydantic import ValidationError

from app.schemas import ActionRequest
from app.schemas import BotActionRequest
from app.schemas import BotTimeoutRequest


def test_action_request_accepts_optional_hand_index() -> None:
    payload = ActionRequest(position=1, action="hit", hand_index=0)
    assert payload.hand_index == 0


def test_action_request_defaults_hand_index_to_none() -> None:
    payload = ActionRequest(position=1, action="stand")
    assert payload.hand_index is None


def test_action_request_rejects_negative_hand_index() -> None:
    with pytest.raises(ValidationError):
        ActionRequest(position=1, action="hit", hand_index=-1)


def test_bot_action_request_accepts_optional_hand_index() -> None:
    payload = BotActionRequest(
        chat_id="chat-1",
        chat_type="single",
        actor_telegram_id="tg-1",
        action="double",
        turn_version=2,
        hand_index=1,
    )
    assert payload.hand_index == 1


def test_bot_action_request_defaults_hand_index_to_none() -> None:
    payload = BotActionRequest(
        chat_id="chat-1",
        chat_type="single",
        actor_telegram_id="tg-1",
        action="hit",
        turn_version=2,
    )
    assert payload.hand_index is None


def test_bot_timeout_request_accepts_optional_hand_index() -> None:
    payload = BotTimeoutRequest(
        chat_id="chat-1",
        chat_type="single",
        turn_version=2,
        hand_index=1,
    )
    assert payload.hand_index == 1


def test_bot_timeout_request_defaults_hand_index_to_none() -> None:
    payload = BotTimeoutRequest(
        chat_id="chat-1",
        chat_type="single",
        turn_version=2,
    )
    assert payload.hand_index is None
