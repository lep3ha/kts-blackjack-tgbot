import asyncio

from app.models import SessionStatus
from app.domain.blackjack.context import BlackjackSessionContext, PlayerSlotSnapshot
from app.services.blackjack_service import BlackjackService


class FakeRepository:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def persist_player_move(self, context, *, position, action, cards, bet, next_position, next_timer, details):
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
