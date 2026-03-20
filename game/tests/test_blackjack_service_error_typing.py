import pytest

from app.errors import StateConflictError
from app.models import ChatMode, ParticipantStatus, SessionStatus
from app.domain.blackjack.context import BlackjackSessionContext, PlayerSlotSnapshot
from app.services.blackjack_service import BlackjackService


class DummyRepository:
    async def commit(self):
        pass

    async def rollback(self):
        pass


def test_validate_can_start_empty_session_is_state_conflict():
    context = BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.lobby_open,
        state="waiting",
        chat_mode=ChatMode.group,
        players=[],
    )
    service = BlackjackService(repository=DummyRepository(), model=context)

    with pytest.raises(StateConflictError):
        service.validate_can_start()


def test_available_moves_filters_unavailable_actions_without_raising():
    context = BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        chat_mode=ChatMode.group,
        current_position=1,
        players=[
            PlayerSlotSnapshot(
                player_to_session_id=1,
                player_id=10,
                position=1,
                bet=100,
                participant_status=ParticipantStatus.active,
                cards=["AS", "KD", "5H"],
                bank=1000,
            )
        ],
    )

    service = BlackjackService(repository=DummyRepository(), model=context)

    moves = service.available_moves()
    assert "hit" in moves
    assert "stand" in moves
    assert "double" not in moves


def test_available_moves_excludes_double_when_bank_insufficient_for_double():
    context = BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        chat_mode=ChatMode.group,
        current_position=1,
        players=[
            PlayerSlotSnapshot(
                player_to_session_id=1,
                player_id=10,
                position=1,
                bet=100,
                participant_status=ParticipantStatus.active,
                cards=["9S", "2H"],
                bank=100,
            )
        ],
    )

    service = BlackjackService(repository=DummyRepository(), model=context)

    moves = service.available_moves()
    assert "hit" in moves
    assert "stand" in moves
    assert "double" not in moves


def test_available_moves_includes_insurance_only_when_dealer_shows_ace():
    ace_context = BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        chat_mode=ChatMode.group,
        dealer_cards=["AS", "9H"],
        current_position=1,
        players=[
            PlayerSlotSnapshot(
                player_to_session_id=1,
                player_id=10,
                position=1,
                bet=100,
                participant_status=ParticipantStatus.active,
                cards=["9S", "2H"],
                bank=1000,
            )
        ],
    )
    no_ace_context = BlackjackSessionContext(
        session_id=2,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        chat_mode=ChatMode.group,
        dealer_cards=["9S", "AH"],
        current_position=1,
        players=[
            PlayerSlotSnapshot(
                player_to_session_id=1,
                player_id=10,
                position=1,
                bet=100,
                participant_status=ParticipantStatus.active,
                cards=["9S", "2H"],
                bank=1000,
            )
        ],
    )

    ace_service = BlackjackService(repository=DummyRepository(), model=ace_context)
    no_ace_service = BlackjackService(repository=DummyRepository(), model=no_ace_context)

    assert "insurance" in ace_service.available_moves()
    assert "insurance" not in no_ace_service.available_moves()
