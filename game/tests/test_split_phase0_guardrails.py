import pytest

from app.schemas import ActionRequest
from app.schemas import BotActionRequest


def test_action_request_accepts_split_in_next_phase() -> None:
    payload = ActionRequest(position=1, action="split")
    assert payload.action == "split"


def test_bot_action_request_accepts_split_in_next_phase() -> None:
    payload = BotActionRequest(
        chat_id="chat-1",
        chat_type="single",
        actor_telegram_id="tg-1",
        action="split",
        turn_version=1,
    )
    assert payload.action == "split"


