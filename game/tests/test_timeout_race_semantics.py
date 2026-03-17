import asyncio

import pytest

import app.accessors.bot_accessor as bot_module
from app.accessors.bot_accessor import BotGameAccessor
from app.domain.blackjack.turn_rules import PlayerTurnRules
from app.errors import StateConflictError
from app.models import ChatMode, ParticipantStatus, SessionStatus
from app.domain.blackjack.context import BlackjackSessionContext, PlayerSlotSnapshot
from app.services.blackjack_service import compute_score
from app.schemas import BotTimeoutRequest


def _rules() -> PlayerTurnRules:
    return PlayerTurnRules(score_fn=compute_score, player_actions=frozenset({"hit", "stand", "double"}))


def test_validate_timeout_request_requires_active_current_player_and_expired_timer():
    rules = _rules()

    context = BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        chat_mode=ChatMode.group,
        current_position=2,
        players=[],
    )

    seat = PlayerSlotSnapshot(
        player_to_session_id=1,
        player_id=10,
        position=2,
        bet=100,
        participant_status=ParticipantStatus.active,
        cards=["9S", "2H"],
        bank=1000,
    )

    with pytest.raises(StateConflictError):
        rules.validate_timeout_request(context, position=2, seat=seat, timer_expired=False)

    seat_inactive = PlayerSlotSnapshot(
        player_to_session_id=2,
        player_id=11,
        position=2,
        bet=100,
        participant_status=ParticipantStatus.inactive,
        cards=["9S", "2H"],
        bank=1000,
    )
    with pytest.raises(StateConflictError):
        rules.validate_timeout_request(context, position=2, seat=seat_inactive, timer_expired=True)

    with pytest.raises(StateConflictError):
        rules.validate_timeout_request(context, position=1, seat=seat, timer_expired=True)


def test_bot_timeout_noop_for_inactive_or_settled_current_player(monkeypatch):
    class DummySession:
        id = 123
        status = SessionStatus.in_progress
        chat_mode = ChatMode.single

    class DummyModel:
        def __init__(self, seat_status: ParticipantStatus):
            self.turn_version = 10
            self.current_position = 1
            self._seat_status = seat_status

        def player_by_position(self, position):
            if position != 1:
                return None
            return PlayerSlotSnapshot(
                player_to_session_id=1,
                player_id=10,
                position=1,
                bet=100,
                participant_status=self._seat_status,
                cards=["9S", "2H"],
                bank=1000,
            )

    class DummyMachine:
        def __init__(self, seat_status: ParticipantStatus):
            self.model = DummyModel(seat_status)

    async def fake_get_db():
        yield object()

    async def fake_get_unfinished_session_by_chat_id(self, db, chat_id, *, chat_mode=None):
        return DummySession()

    async def fake_build_session_snapshot(self, db, session_id):
        return {"ok": True, "session_id": session_id}

    async def fake_load(db, session_id, *, turn_timeout_seconds=30, for_update=True):
        return DummyMachine(ParticipantStatus.inactive)

    monkeypatch.setattr(bot_module, "get_db", fake_get_db)
    monkeypatch.setattr(BotGameAccessor, "_get_unfinished_session_by_chat_id", fake_get_unfinished_session_by_chat_id)
    monkeypatch.setattr(BotGameAccessor, "_build_session_snapshot", fake_build_session_snapshot)
    monkeypatch.setattr(bot_module.BlackjackService, "load", staticmethod(fake_load))

    payload = BotTimeoutRequest(chat_id="chat-1", chat_type="single", turn_version=10)

    async def run():
        accessor = BotGameAccessor()
        data = await accessor.apply_timeout(payload)
        assert data == {"ok": True, "session_id": 123}

    asyncio.run(run())


def test_bot_timeout_requires_active_turn(monkeypatch):
    class DummySession:
        id = 123
        status = SessionStatus.in_progress
        chat_mode = ChatMode.single

    class DummyModel:
        turn_version = 10
        current_position = None

    class DummyMachine:
        model = DummyModel()

    async def fake_get_db():
        yield object()

    async def fake_get_unfinished_session_by_chat_id(self, db, chat_id, *, chat_mode=None):
        return DummySession()

    async def fake_load(db, session_id, *, turn_timeout_seconds=30, for_update=True):
        return DummyMachine()

    monkeypatch.setattr(bot_module, "get_db", fake_get_db)
    monkeypatch.setattr(BotGameAccessor, "_get_unfinished_session_by_chat_id", fake_get_unfinished_session_by_chat_id)
    monkeypatch.setattr(bot_module.BlackjackService, "load", staticmethod(fake_load))

    payload = BotTimeoutRequest(chat_id="chat-1", chat_type="single", turn_version=10)

    async def run():
        accessor = BotGameAccessor()
        with pytest.raises(StateConflictError):
            await accessor.apply_timeout(payload)

    asyncio.run(run())
