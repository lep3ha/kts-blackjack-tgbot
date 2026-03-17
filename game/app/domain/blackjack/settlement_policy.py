"""Settlement policy for blackjack payouts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models import ParticipantStatus
from app.domain.blackjack.context import PlayerSlotSnapshot


@dataclass(slots=True)
class SettlementPolicy:
    """Calculates round outcomes and balance deltas."""

    score_fn: Callable[[list[str]], tuple[int, bool]]

    def build_settlements(self, players: list[PlayerSlotSnapshot], dealer_cards: list[str]) -> list[dict[str, int | str]]:
        dealer_score, dealer_blackjack = self.score_fn(dealer_cards)
        settlements: list[dict[str, int | str]] = []

        for player in players:
            if player.participant_status != ParticipantStatus.active:
                continue
            player_score, player_blackjack = self.score_fn(player.cards)
            if player_blackjack and not dealer_blackjack:
                result = "blackjack"
                delta = int(player.bet * 3 / 2)
            elif player_score > 21:
                result = "bust"
                delta = -player.bet
            elif dealer_score > 21:
                result = "win"
                delta = player.bet
            elif player_score > dealer_score:
                result = "win"
                delta = player.bet
            elif player_score == dealer_score:
                result = "push"
                delta = 0
            else:
                result = "lose"
                delta = -player.bet

            settlements.append({"position": player.position, "result": result, "delta": delta})

        return settlements
