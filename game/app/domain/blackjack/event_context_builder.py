"""Builder for state machine event runtime context."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Callable, Optional

from app.domain.blackjack.context import BlackjackSessionContext


@dataclass(slots=True)
class EventContextBuilder:
    """Creates a normalized context payload for state machine callbacks."""

    draw_card_fn: Callable[[], str]
    score_fn: Callable[[list[str]], tuple[int, bool]]
    next_playable_position_fn: Callable[[list, Optional[int]], Optional[int]]
    _draw_cache: dict[tuple[int, int, str], str] = field(default_factory=dict, repr=False)

    def build(
        self,
        *,
        model: BlackjackSessionContext,
        event_id: Optional[str],
        event_token: Optional[int],
        position: Optional[int],
        action: Optional[str],
    ) -> dict:
        resolved_position = position if position is not None else model.current_position
        resolved_action = "timeout" if event_id == "timeout_turn" else action
        seat = model.player_by_position(resolved_position)

        drawn_card = None
        projected_cards = list(seat.cards) if seat else []
        if seat and resolved_action in {"hit", "double"}:
            cache_key = (event_token or 0, resolved_position, resolved_action)
            drawn_card = self._draw_cache.get(cache_key)
            if drawn_card is None:
                drawn_card = self.draw_card_fn()
                self._draw_cache[cache_key] = drawn_card
            projected_cards.append(drawn_card)

        projected_score, projected_blackjack = self.score_fn(projected_cards) if seat else (0, False)
        next_position = self.next_playable_position_fn(model.players, resolved_position)

        return {
            "position": resolved_position,
            "action": resolved_action,
            "seat": seat,
            "drawn_card": drawn_card,
            "projected_cards": projected_cards,
            "projected_score": projected_score,
            "projected_blackjack": projected_blackjack,
            "next_position": next_position,
        }
