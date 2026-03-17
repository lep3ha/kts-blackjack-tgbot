"""Dealer play policy for blackjack rounds."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class DealerPolicy:
    """Encapsulates dealer draw/stand behavior."""

    score_fn: Callable[[list[str]], tuple[int, bool]]
    draw_card_fn: Callable[[], str]
    stand_score: int = 17

    def play_turn(self, dealer_cards: list[str]) -> tuple[list[str], list[str]]:
        current_cards = list(dealer_cards)
        drawn_cards: list[str] = []

        while True:
            score, _ = self.score_fn(current_cards)
            if score < self.stand_score:
                card = self.draw_card_fn()
                current_cards.append(card)
                drawn_cards.append(card)
                continue
            break

        return current_cards, drawn_cards
