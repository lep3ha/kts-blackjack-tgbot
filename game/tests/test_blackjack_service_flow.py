import asyncio
from datetime import timedelta

import pytest

from app.core.datetime_utils import utc_now_naive
from app.errors import StateConflictError
from app.models import SessionStatus
from app.domain.blackjack.context import BlackjackSessionContext, PlayerSlotSnapshot
from app.services.blackjack_service import BlackjackService


class FakeRepository:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.last_action = None
        self.last_details = None

    async def persist_player_move(self, context, *, position, action, cards, bet, next_position, next_timer, details):
        self.last_action = action
        self.last_details = dict(details or {})
        player = context.player_by_position(position)
        player.cards = list(cards)
        player.bet = bet
        context.current_position = next_position
        context.current_timer = next_timer

    async def persist_timeout(self, context, *, position, next_position, next_timer):
        context.current_position = next_position
        context.current_timer = next_timer

    async def persist_dealer_turn(self, context, *, dealer_cards, drawn_cards):
        context.dealer_cards = list(dealer_cards)

    async def persist_resolution(self, context, *, settlements):
        context.status = SessionStatus.closed
        context.current_position = None
        context.current_timer = None

    async def load_unsettled_hands_by_position(self, session_id):
        return {}

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def test_apply_action_auto_closes_round(monkeypatch):
    # Детеминированный добор карты без исчерпания генератора.
    monkeypatch.setattr("app.services.blackjack_service.draw_card", lambda: "KS")

    context = BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        dealer_cards=["9S", "7H"],
        current_position=1,
        current_timer=None,
        players=[
            PlayerSlotSnapshot(
                player_to_session_id=1,
                player_id=101,
                position=1,
                bet=10,
                cards=["8S", "8H"],
                bank=100,
            )
        ],
    )
    repository = FakeRepository()
    machine = BlackjackService(repository=repository, model=context)

    result = asyncio.run(machine.apply_action(position=1, action="hit"))

    assert result.status == SessionStatus.closed
    assert machine.closed.is_active
    assert repository.committed is True
    assert repository.rolled_back is False


def test_available_moves_includes_split_when_pair_and_bank_is_sufficient():
    context = BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        dealer_cards=["9S", "7H"],
        current_position=1,
        current_timer=None,
        players=[
            PlayerSlotSnapshot(
                player_to_session_id=1,
                player_id=101,
                position=1,
                bet=100,
                cards=["8S", "8H"],
                bank=300,
            )
        ],
    )
    repository = FakeRepository()
    machine = BlackjackService(repository=repository, model=context)

    moves = machine.available_moves()
    assert "split" in moves


def test_handle_timeout_defaults_to_current_position_and_closes_round(monkeypatch):
    monkeypatch.setattr("app.services.blackjack_service.draw_card", lambda: "KS")

    context = BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        dealer_cards=["9S", "7H"],
        current_position=1,
        current_timer=utc_now_naive() - timedelta(seconds=1),
        players=[
            PlayerSlotSnapshot(
                player_to_session_id=1,
                player_id=101,
                position=1,
                bet=10,
                cards=["10S", "6H"],
                bank=100,
            )
        ],
    )
    repository = FakeRepository()
    machine = BlackjackService(repository=repository, model=context)

    result = asyncio.run(machine.handle_timeout())

    assert result.status == SessionStatus.closed
    assert machine.closed.is_active
    assert repository.committed is True
    assert repository.rolled_back is False


def test_handle_timeout_rejects_when_timer_not_expired_and_rolls_back():
    context = BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        dealer_cards=["9S", "7H"],
        current_position=1,
        current_timer=utc_now_naive() + timedelta(seconds=30),
        players=[
            PlayerSlotSnapshot(
                player_to_session_id=1,
                player_id=101,
                position=1,
                bet=10,
                cards=["10S", "6H"],
                bank=100,
            )
        ],
    )
    repository = FakeRepository()
    machine = BlackjackService(repository=repository, model=context)

    with pytest.raises(StateConflictError):
        asyncio.run(machine.handle_timeout())

    assert repository.committed is False
    assert repository.rolled_back is True


def test_apply_insurance_keeps_player_turn_and_emits_insurance_details():
    context = BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        dealer_cards=["AS", "7H"],
        current_position=1,
        current_timer=utc_now_naive() + timedelta(seconds=30),
        players=[
            PlayerSlotSnapshot(
                player_to_session_id=1,
                player_id=101,
                position=1,
                bet=100,
                cards=["10S", "6H"],
                bank=1000,
            )
        ],
    )
    repository = FakeRepository()
    machine = BlackjackService(repository=repository, model=context)

    result = asyncio.run(machine.apply_action(position=1, action="insurance"))

    assert result.status == SessionStatus.in_progress
    assert machine.player_turn.is_active
    assert repository.last_action == "insurance"
    assert repository.last_details is not None
    assert repository.last_details.get("insurance_bet") == 50
