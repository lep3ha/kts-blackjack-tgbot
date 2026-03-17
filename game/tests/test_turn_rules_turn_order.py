from app.domain.blackjack.turn_rules import PlayerTurnRules
from app.models import ParticipantStatus
from app.domain.blackjack.context import PlayerSlotSnapshot
from app.services.blackjack_service import compute_score


def _rules() -> PlayerTurnRules:
    return PlayerTurnRules(score_fn=compute_score, player_actions=frozenset({"hit", "stand", "double"}))


def test_first_playable_position_skips_inactive_and_settled():
    rules = _rules()

    players = [
        PlayerSlotSnapshot(
            player_to_session_id=1,
            player_id=101,
            position=1,
            bet=100,
            participant_status=ParticipantStatus.inactive,
            cards=["2S", "3H"],
            bank=1000,
        ),
        PlayerSlotSnapshot(
            player_to_session_id=2,
            player_id=102,
            position=2,
            bet=100,
            participant_status=ParticipantStatus.settled,
            cards=["2S", "3H"],
            bank=1000,
        ),
        PlayerSlotSnapshot(
            player_to_session_id=3,
            player_id=103,
            position=3,
            bet=100,
            participant_status=ParticipantStatus.active,
            cards=["2S", "3H"],
            bank=1000,
        ),
    ]

    assert rules.first_playable_position(players) == 3


def test_first_playable_position_skips_blackjack_and_bust():
    rules = _rules()

    players = [
        PlayerSlotSnapshot(
            player_to_session_id=1,
            player_id=201,
            position=1,
            bet=100,
            participant_status=ParticipantStatus.active,
            cards=["AS", "KH"],  # blackjack
            bank=1000,
        ),
        PlayerSlotSnapshot(
            player_to_session_id=2,
            player_id=202,
            position=2,
            bet=100,
            participant_status=ParticipantStatus.active,
            cards=["10S", "9H", "5D"],  # bust
            bank=1000,
        ),
        PlayerSlotSnapshot(
            player_to_session_id=3,
            player_id=203,
            position=3,
            bet=100,
            participant_status=ParticipantStatus.active,
            cards=["9S", "2H"],
            bank=1000,
        ),
    ]

    assert rules.first_playable_position(players) == 3


def test_next_playable_position_skips_non_playable_after_current():
    rules = _rules()

    players = [
        PlayerSlotSnapshot(
            player_to_session_id=1,
            player_id=301,
            position=1,
            bet=100,
            participant_status=ParticipantStatus.active,
            cards=["9S", "2H"],
            bank=1000,
        ),
        PlayerSlotSnapshot(
            player_to_session_id=2,
            player_id=302,
            position=2,
            bet=100,
            participant_status=ParticipantStatus.inactive,
            cards=["9S", "2H"],
            bank=1000,
        ),
        PlayerSlotSnapshot(
            player_to_session_id=3,
            player_id=303,
            position=3,
            bet=100,
            participant_status=ParticipantStatus.active,
            cards=["AS", "KH"],  # blackjack => cannot act
            bank=1000,
        ),
        PlayerSlotSnapshot(
            player_to_session_id=4,
            player_id=304,
            position=4,
            bet=100,
            participant_status=ParticipantStatus.active,
            cards=["5S", "6H"],
            bank=1000,
        ),
    ]

    assert rules.next_playable_position(players, current_position=1) == 4
