import pytest

from app.domain.blackjack.action_dispatch import ActionRuntimeContext
from app.domain.blackjack.action_dispatch import PlayerActionDispatcher
from app.domain.blackjack.context import BlackjackSessionContext
from app.domain.blackjack.context import PlayerSlotSnapshot
from app.domain.blackjack.turn_rules import PlayerTurnRules
from app.errors import GameLogicError
from app.models import ChatMode
from app.models import ParticipantStatus
from app.models import SessionStatus
from app.services.blackjack_service import compute_score


def _rules() -> PlayerTurnRules:
    return PlayerTurnRules(score_fn=compute_score, player_actions=frozenset({"hit", "stand", "double", "split"}))


def _context() -> BlackjackSessionContext:
    return BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        chat_mode=ChatMode.single,
        current_position=1,
        players=[],
    )


def _seat(*, cards: list[str], bank: int = 1000, bet: int = 100) -> PlayerSlotSnapshot:
    return PlayerSlotSnapshot(
        player_to_session_id=1,
        player_id=1,
        position=1,
        bet=bet,
        participant_status=ParticipantStatus.active,
        cards=cards,
        bank=bank,
    )


def test_split_is_allowed_for_pair_and_sufficient_bank() -> None:
    rules = _rules()
    rules.validate_player_move(_context(), position=1, action="split", seat=_seat(cards=["8S", "8H"], bank=500, bet=100))


def test_split_rejected_when_cards_not_pair() -> None:
    rules = _rules()
    with pytest.raises(GameLogicError):
        rules.validate_player_move(_context(), position=1, action="split", seat=_seat(cards=["8S", "9H"], bank=500, bet=100))


def test_split_rejected_when_bank_insufficient() -> None:
    rules = _rules()
    with pytest.raises(GameLogicError):
        rules.validate_player_move(_context(), position=1, action="split", seat=_seat(cards=["8S", "8H"], bank=150, bet=100))


def test_split_rejected_when_not_two_cards() -> None:
    rules = _rules()
    with pytest.raises(GameLogicError):
        rules.validate_player_move(_context(), position=1, action="split", seat=_seat(cards=["8S", "8H", "2D"], bank=500, bet=100))


def test_split_dispatch_keeps_turn_on_same_position() -> None:
    dispatcher = PlayerActionDispatcher()
    seat = _seat(cards=["8S", "8H"], bank=500, bet=100)
    result = dispatcher.dispatch(
        ActionRuntimeContext(
            position=1,
            action="split",
            hand_index=0,
            seat=seat,
            target_state_id="player_turn",
            drawn_card=None,
            split_drawn_cards=["2D", "3C"],
            projected_cards=list(seat.cards),
            projected_score=16,
            next_position=2,
            dealer_blackjack=False,
        )
    )

    assert result.next_position == 1
    assert result.should_schedule_timer is True
    assert result.details.get("split_requested") is True
    assert result.cards == ["8S", "2D"]
    assert result.details.get("split_second_hand_cards") == ["8H"]
    assert result.details.get("split_second_hand_draw_card") == "3C"
