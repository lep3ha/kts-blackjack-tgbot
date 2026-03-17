import asyncio

import pytest

import app.accessors.bot_accessor as bot_module
from app.accessors.bot_accessor import BotGameAccessor
from app.errors import BadRequestError, StateConflictError
from app.models import ChatMode, SessionStatus
from app.schemas import GroupLobbyStartRequest


def test_chat_type_mismatch_is_bad_request():
    accessor = BotGameAccessor()
    with pytest.raises(BadRequestError):
        accessor._ensure_group_chat("single")
    with pytest.raises(BadRequestError):
        accessor._ensure_single_chat("group")


def test_unsupported_chat_type_is_bad_request():
    accessor = BotGameAccessor()
    with pytest.raises(BadRequestError):
        accessor._chat_mode_from_type("channel")


def test_start_group_lobby_empty_participants_is_state_conflict(monkeypatch):
    class DummySession:
        id = 123
        status = SessionStatus.lobby_open
        chat_mode = ChatMode.group

    async def fake_get_db():
        yield object()

    async def fake_get_unfinished_session_by_chat_id(self, db, chat_id, *, chat_mode=None):
        return DummySession()

    async def fake_get_session_participants(self, db, session_id):
        return []

    monkeypatch.setattr(bot_module, "get_db", fake_get_db)
    monkeypatch.setattr(BotGameAccessor, "_get_unfinished_session_by_chat_id", fake_get_unfinished_session_by_chat_id)
    monkeypatch.setattr(BotGameAccessor, "_get_session_participants", fake_get_session_participants)

    payload = GroupLobbyStartRequest(
        chat_id="chat-1",
        chat_type="group",
        actor_telegram_id="tg-admin",
        actor_is_admin=True,
    )

    async def run():
        accessor = BotGameAccessor()
        with pytest.raises(StateConflictError):
            await accessor.start_group_lobby(payload)

    asyncio.run(run())
