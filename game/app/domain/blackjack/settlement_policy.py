"""Settlement policy for blackjack payouts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from typing import Optional

from app.models import ParticipantStatus
from app.domain.blackjack.context import PlayerSlotSnapshot


@dataclass(slots=True)
class SettlementPolicy:
    """Calculates round outcomes and balance deltas."""

    score_fn: Callable[[list[str]], tuple[int, bool]]

    def build_settlements(
        self,
        players: list[PlayerSlotSnapshot],
        dealer_cards: list[str],
        hands_by_position: Optional[dict[int, list[dict[str, int | str | list[str]]]]] = None,
    ) -> list[dict[str, int | str | list[dict[str, int | str]]]]:
        dealer_score, dealer_blackjack = self.score_fn(dealer_cards)
        settlements: list[dict[str, int | str | list[dict[str, int | str]]]] = []

        for player in players:
            if player.participant_status != ParticipantStatus.active:
                continue

            resolved_hands = list((hands_by_position or {}).get(player.position, []))
            if not resolved_hands:
                resolved_hands = [{"hand_index": 0, "cards": list(player.cards), "bet": player.bet}]

            hand_settlements: list[dict[str, int | str]] = []
            for hand in resolved_hands:
                hand_cards = list(hand.get("cards") or [])
                hand_bet = int(hand.get("bet") or 0)
                hand_result, hand_delta = self._evaluate_hand(
                    hand_cards,
                    hand_bet,
                    dealer_score=dealer_score,
                    dealer_blackjack=dealer_blackjack,
                )
                hand_settlements.append(
                    {
                        "hand_index": int(hand.get("hand_index") or 0),
                        "result": hand_result,
                        "delta": hand_delta,
                    }
                )

            aggregate_delta = sum(int(entry["delta"]) for entry in hand_settlements)
            insurance_delta = 0
            if dealer_blackjack and player.insurance_bet > 0:
                # Insurance stake is deducted when purchased; payout on dealer blackjack is 2:1,
                # so settlement credits stake + winnings here.
                insurance_delta = int(player.insurance_bet) * 3
            aggregate_delta += insurance_delta

            aggregate_result = self._aggregate_result(hand_settlements)
            if insurance_delta > 0:
                if aggregate_delta > 0:
                    aggregate_result = "win"
                elif aggregate_delta == 0:
                    aggregate_result = "push"

            settlements.append(
                {
                    "position": player.position,
                    "result": aggregate_result,
                    "delta": aggregate_delta,
                    "hand_settlements": hand_settlements,
                    "insurance_delta": insurance_delta,
                }
            )

        return settlements

    def _evaluate_hand(
        self,
        cards: list[str],
        bet: int,
        *,
        dealer_score: int,
        dealer_blackjack: bool,
    ) -> tuple[str, int]:
        player_score, player_blackjack = self.score_fn(cards)
        if player_blackjack and not dealer_blackjack:
            return "blackjack", int(bet * 3 / 2)
        if player_score > 21:
            return "bust", -bet
        if dealer_score > 21:
            return "win", bet
        if player_score > dealer_score:
            return "win", bet
        if player_score == dealer_score:
            return "push", 0
        return "lose", -bet

    def _aggregate_result(self, hand_settlements: list[dict[str, int | str]]) -> str:
        if len(hand_settlements) == 1:
            return str(hand_settlements[0]["result"])

        has_positive = any(int(item["delta"]) > 0 for item in hand_settlements)
        has_negative = any(int(item["delta"]) < 0 for item in hand_settlements)
        if has_positive and has_negative:
            return "mixed"
        if has_positive:
            return "win"
        if has_negative:
            return "lose"
        return "push"
