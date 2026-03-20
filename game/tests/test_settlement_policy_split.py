from app.domain.blackjack.context import PlayerSlotSnapshot
from app.domain.blackjack.settlement_policy import SettlementPolicy
from app.models import ParticipantStatus
from app.services.blackjack_service import compute_score


def _active_player(*, position: int = 1, bet: int = 100, cards: list[str] | None = None) -> PlayerSlotSnapshot:
    return PlayerSlotSnapshot(
        player_to_session_id=10 + position,
        player_id=100 + position,
        position=position,
        bet=bet,
        participant_status=ParticipantStatus.active,
        cards=list(cards or ["8S", "8H"]),
        bank=1000,
    )


def test_settlement_policy_aggregates_split_hands_to_mixed_when_deltas_cancel() -> None:
    policy = SettlementPolicy(score_fn=compute_score)
    players = [_active_player(position=1, bet=100)]

    settlements = policy.build_settlements(
        players,
        dealer_cards=["10S", "8H"],
        hands_by_position={
            1: [
                {"hand_index": 0, "cards": ["10D", "9C"], "bet": 100},
                {"hand_index": 1, "cards": ["9D", "8C"], "bet": 100},
            ]
        },
    )

    assert len(settlements) == 1
    settlement = settlements[0]
    assert settlement["position"] == 1
    assert settlement["delta"] == 0
    assert settlement["result"] == "mixed"

    hands = settlement["hand_settlements"]
    assert isinstance(hands, list)
    assert len(hands) == 2
    assert hands[0]["hand_index"] == 0
    assert hands[0]["result"] == "win"
    assert hands[0]["delta"] == 100
    assert hands[1]["hand_index"] == 1
    assert hands[1]["result"] == "lose"
    assert hands[1]["delta"] == -100


def test_settlement_policy_keeps_single_hand_result_shape() -> None:
    policy = SettlementPolicy(score_fn=compute_score)
    players = [_active_player(position=1, bet=100, cards=["KD", "9C", "5S"])]

    settlements = policy.build_settlements(players, dealer_cards=["10S", "7H"])

    assert len(settlements) == 1
    settlement = settlements[0]
    assert settlement["result"] == "bust"
    assert settlement["delta"] == -100
    assert settlement["hand_settlements"] == [{"hand_index": 0, "result": "bust", "delta": -100}]


def test_settlement_policy_applies_insurance_payout_when_dealer_has_blackjack() -> None:
    policy = SettlementPolicy(score_fn=compute_score)
    player = _active_player(position=1, bet=100, cards=["10D", "9C"])
    player.insurance_bet = 50

    settlements = policy.build_settlements(players=[player], dealer_cards=["AS", "KC"])

    assert len(settlements) == 1
    settlement = settlements[0]
    assert settlement["insurance_delta"] == 150
    assert settlement["delta"] == 50
    assert settlement["result"] == "win"


def test_settlement_policy_does_not_pay_insurance_when_dealer_has_no_blackjack() -> None:
    policy = SettlementPolicy(score_fn=compute_score)
    player = _active_player(position=1, bet=100, cards=["10D", "9C"])
    player.insurance_bet = 50

    settlements = policy.build_settlements(players=[player], dealer_cards=["AS", "9C"])

    assert len(settlements) == 1
    settlement = settlements[0]
    assert settlement["insurance_delta"] == 0
    assert settlement["delta"] == -100
    assert settlement["result"] == "lose"
