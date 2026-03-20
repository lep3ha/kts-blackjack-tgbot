import asyncio
from unittest.mock import AsyncMock

from app.domain.blackjack.context import BlackjackSessionContext, PlayerSlotSnapshot
from app.models import ParticipantStatus, SessionStatus
from app.services.blackjack_repository import BlackjackRepository


def _build_context() -> BlackjackSessionContext:
    return BlackjackSessionContext(
        session_id=1,
        deck_id=1,
        status=SessionStatus.in_progress,
        state="player_turn",
        turn_version=0,
        dealer_cards=["9S", "7H"],
        current_position=1,
        current_hand_index=0,
        players=[
            PlayerSlotSnapshot(
                player_to_session_id=11,
                player_id=101,
                position=1,
                bet=100,
                cards=["8S", "8H"],
                bank=1000,
                participant_status=ParticipantStatus.active,
            )
        ],
    )


def test_persist_move_switches_to_next_hand_when_available():
    db = AsyncMock()
    repo = BlackjackRepository(db=db)
    repo.session_id = 1
    repo._append_state = AsyncMock()
    repo._upsert_hand = AsyncMock()
    repo._sync_primary_hand_status = AsyncMock()
    repo._next_active_hand_index = AsyncMock(return_value=1)
    repo._materialize_delayed_split_card = AsyncMock()
    repo._load_hand = AsyncMock(return_value=None)

    context = _build_context()

    asyncio.run(
        repo.persist_player_move(
            context,
            position=1,
            action="stand",
            cards=["8S", "8H"],
            bet=100,
            next_position=2,
            next_timer=None,
            details={"actor": "player"},
        )
    )

    assert context.current_position == 1
    assert context.current_hand_index == 1
    assert context.current_timer is not None
    repo._sync_primary_hand_status.assert_awaited_once_with(
        player_to_session_id=11,
        participant_status=ParticipantStatus.inactive,
        hand_index=0,
    )


def test_persist_move_keeps_next_player_when_no_extra_hand():
    db = AsyncMock()
    repo = BlackjackRepository(db=db)
    repo.session_id = 1
    repo._append_state = AsyncMock()
    repo._upsert_hand = AsyncMock()
    repo._sync_primary_hand_status = AsyncMock()
    repo._next_active_hand_index = AsyncMock(return_value=None)
    repo._materialize_delayed_split_card = AsyncMock()

    context = _build_context()

    asyncio.run(
        repo.persist_player_move(
            context,
            position=1,
            action="stand",
            cards=["8S", "8H"],
            bet=100,
            next_position=2,
            next_timer=None,
            details={"actor": "player"},
        )
    )

    assert context.current_position == 2
    assert context.current_hand_index == 0
    repo._sync_primary_hand_status.assert_not_awaited()


def test_persist_move_split_creates_second_hand_and_keeps_current_hand():
    db = AsyncMock()
    repo = BlackjackRepository(db=db)
    repo.session_id = 1
    repo._append_state = AsyncMock()
    repo._upsert_hand = AsyncMock()
    repo._sync_primary_hand_status = AsyncMock()
    repo._next_active_hand_index = AsyncMock(return_value=None)
    repo._count_hands = AsyncMock(return_value=1)
    repo._shift_hands_right = AsyncMock()

    context = _build_context()

    asyncio.run(
        repo.persist_player_move(
            context,
            position=1,
            action="split",
            cards=["8S", "2D"],
            bet=100,
            next_position=1,
            next_timer=None,
            details={
                "actor": "player",
                "split_second_hand_cards": ["8H"],
                "split_second_hand_draw_card": "3C",
            },
        )
    )

    assert context.current_position == 1
    assert context.current_hand_index == 0
    assert repo._upsert_hand.await_count == 2
    repo._sync_primary_hand_status.assert_not_awaited()
