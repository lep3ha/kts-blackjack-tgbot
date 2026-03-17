import asyncio
from datetime import datetime

import pytest

import app.accessors.bot.group as bot_group_module
from app.accessors.bot import BotGameAccessor
from app.models import ChatMode, ParticipantStatus, SessionStatus
from app.schemas import GroupPlayerStopRequest
from app.domain.blackjack.context import PlayerSlotSnapshot


class DummyRepository:
    def __init__(self):
        self.persist_partial_settlement_calls = []
        self.committed = False

    async def persist_partial_settlement(
        self,
        model,
        *,
        position,
        participant_status,
        settlement,
        next_position,
        next_timer,
        close_session,
    ):
        self.persist_partial_settlement_calls.append(
            {
                "position": position,
                "participant_status": participant_status,
                "settlement": settlement,
                "next_position": next_position,
                "next_timer": next_timer,
                "close_session": close_session,
            }
        )

    async def commit(self):
        self.committed = True


class DummySettlementPolicy:
    def build_settlements(self, seats, dealer_cards):
        return [{"result": "stopped", "delta": 0} for _ in seats]


class DummyTurnRules:
    def __init__(self, next_position):
        self._next_position = next_position

    def next_playable_position(self, players, current_position):
        return self._next_position


class DummyModel:
    def __init__(
        self,
        *,
        players,
        current_position,
        current_timer,
        turn_timeout_seconds,
        dealer_cards=None,
    ):
        self.players = players
        self.current_position = current_position
        self.current_timer = current_timer
        self.turn_timeout_seconds = turn_timeout_seconds
        self.dealer_cards = dealer_cards or []


class DummyMachine:
    def __init__(self, *, model, repository, settlement_policy, turn_rules):
        self.model = model
        self.repository = repository
        self.settlement_policy = settlement_policy
        self.turn_rules = turn_rules


def test_group_player_stop_outside_own_turn_does_not_reassign_turn(monkeypatch):
    class DummySession:
        id = 123
        status = SessionStatus.in_progress
        chat_mode = ChatMode.group

    async def fake_get_db():
        yield object()

    async def fake_get_unfinished_session_by_chat_id(self, db, chat_id, *, chat_mode=None):
        return DummySession()

    async def fake_build_session_snapshot(self, db, session_id):
        return {"ok": True, "session_id": session_id}

    # Seat(1) stops, but current turn belongs to Seat(2).
    seat1 = PlayerSlotSnapshot(
        player_to_session_id=1,
        player_id=10,
        position=1,
        bet=100,
        participant_status=ParticipantStatus.active,
        cards=["9S", "2H"],
        bank=1000,
    )
    seat2 = PlayerSlotSnapshot(
        player_to_session_id=2,
        player_id=11,
        position=2,
        bet=100,
        participant_status=ParticipantStatus.active,
        cards=["5S", "6H"],
        bank=1000,
    )

    repository = DummyRepository()
    machine = DummyMachine(
        model=DummyModel(
            players=[seat1, seat2],
            current_position=2,
            current_timer=datetime(2020, 1, 1, 0, 0, 0),
            turn_timeout_seconds=30,
            dealer_cards=["9H"],
        ),
        repository=repository,
        settlement_policy=DummySettlementPolicy(),
        turn_rules=DummyTurnRules(next_position=2),
    )

    async def fake_get_machine_player_by_telegram_id(self, db, _machine, telegram_id):
        assert telegram_id == "tg-1"
        return seat1

    async def fake_load(db, session_id, *, turn_timeout_seconds=30, for_update=True):
        assert session_id == 123
        return machine

    monkeypatch.setattr(BotGameAccessor, "_iter_db", lambda self: fake_get_db())
    monkeypatch.setattr(BotGameAccessor, "_get_unfinished_session_by_chat_id", fake_get_unfinished_session_by_chat_id)
    monkeypatch.setattr(BotGameAccessor, "_get_machine_player_by_telegram_id", fake_get_machine_player_by_telegram_id)
    monkeypatch.setattr(BotGameAccessor, "_build_session_snapshot", fake_build_session_snapshot)
    monkeypatch.setattr(bot_group_module.BlackjackService, "load", staticmethod(fake_load))

    payload = GroupPlayerStopRequest(chat_id="chat-1", chat_type="group", actor_telegram_id="tg-1")

    async def run():
        accessor = BotGameAccessor()
        data = await accessor.stop_group_player(payload)
        assert data == {"ok": True, "session_id": 123}

    asyncio.run(run())

    assert repository.committed is True
    assert len(repository.persist_partial_settlement_calls) == 1
    call = repository.persist_partial_settlement_calls[0]
    assert call["position"] == 1
    assert call["participant_status"] == ParticipantStatus.inactive
    assert call["next_position"] == 2
    assert call["next_timer"] == datetime(2020, 1, 1, 0, 0, 0)
    assert call["close_session"] is False


def test_group_player_stop_in_own_turn_reassigns_next_timer(monkeypatch):
    class DummySession:
        id = 123
        status = SessionStatus.in_progress
        chat_mode = ChatMode.group

    fixed_now = datetime(2020, 1, 1, 0, 0, 0)

    async def fake_get_db():
        yield object()

    async def fake_get_unfinished_session_by_chat_id(self, db, chat_id, *, chat_mode=None):
        return DummySession()

    async def fake_build_session_snapshot(self, db, session_id):
        return {"ok": True, "session_id": session_id}

    seat1 = PlayerSlotSnapshot(
        player_to_session_id=1,
        player_id=10,
        position=1,
        bet=100,
        participant_status=ParticipantStatus.active,
        cards=["9S", "2H"],
        bank=1000,
    )
    seat2 = PlayerSlotSnapshot(
        player_to_session_id=2,
        player_id=11,
        position=2,
        bet=100,
        participant_status=ParticipantStatus.active,
        cards=["5S", "6H"],
        bank=1000,
    )

    repository = DummyRepository()
    machine = DummyMachine(
        model=DummyModel(
            players=[seat1, seat2],
            current_position=1,
            current_timer=fixed_now,
            turn_timeout_seconds=30,
            dealer_cards=["9H"],
        ),
        repository=repository,
        settlement_policy=DummySettlementPolicy(),
        turn_rules=DummyTurnRules(next_position=2),
    )

    async def fake_get_machine_player_by_telegram_id(self, db, _machine, telegram_id):
        assert telegram_id == "tg-1"
        return seat1

    async def fake_load(db, session_id, *, turn_timeout_seconds=30, for_update=True):
        return machine

    monkeypatch.setattr(BotGameAccessor, "_iter_db", lambda self: fake_get_db())
    monkeypatch.setattr(BotGameAccessor, "_utc_now_naive", lambda self: fixed_now)
    monkeypatch.setattr(BotGameAccessor, "_get_unfinished_session_by_chat_id", fake_get_unfinished_session_by_chat_id)
    monkeypatch.setattr(BotGameAccessor, "_get_machine_player_by_telegram_id", fake_get_machine_player_by_telegram_id)
    monkeypatch.setattr(BotGameAccessor, "_build_session_snapshot", fake_build_session_snapshot)
    monkeypatch.setattr(bot_group_module.BlackjackService, "load", staticmethod(fake_load))

    payload = GroupPlayerStopRequest(chat_id="chat-1", chat_type="group", actor_telegram_id="tg-1")

    async def run():
        accessor = BotGameAccessor()
        await accessor.stop_group_player(payload)

    asyncio.run(run())

    call = repository.persist_partial_settlement_calls[0]
    assert call["next_position"] == 2
    assert call["next_timer"] == datetime(2020, 1, 1, 0, 0, 30)
