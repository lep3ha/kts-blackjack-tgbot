"""Rules for validating and routing player turns."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from app.errors import BadRequestError, GameLogicError, NotFoundError, StateConflictError
from app.domain.blackjack.context import BlackjackSessionContext, PlayerSlotSnapshot
from app.models import ParticipantStatus, SessionStatus


@dataclass(slots=True)
class PlayerTurnRules:
    """Decision and validation rules for player actions."""

    score_fn: Callable[[list[str]], tuple[int, bool]]
    player_actions: frozenset[str]

    def validate_can_start(self, model: BlackjackSessionContext) -> None:
        if not model.players:
            raise StateConflictError("Session has no players")
        if model.status != SessionStatus.lobby_open:
            raise StateConflictError("Only lobby sessions can be started")

    def validate_player_move(self, model: BlackjackSessionContext, position: int, action: str, seat) -> None:
        if action not in self.player_actions:
            raise BadRequestError("Unsupported player action")
        if seat is None:
            raise NotFoundError("Player not found in session")
        if seat.participant_status != ParticipantStatus.active:
            raise StateConflictError("Only active participants can act")
        if model.current_position != position:
            raise StateConflictError("It is not this player's turn")

        score, blackjack = self.score_fn(seat.cards)
        if blackjack or score >= 21:
            raise StateConflictError("This hand cannot act anymore")

        if action == "double":
            if len(seat.cards) != 2:
                raise GameLogicError("Double is allowed only on the first two cards")
            if seat.bank < seat.bet * 2:
                raise GameLogicError("Insufficient funds to double")

    def validate_timeout_request(self, model: BlackjackSessionContext, position: int, seat, timer_expired: bool) -> None:
        if seat is None:
            raise NotFoundError("Player not found in session")
        if seat.participant_status != ParticipantStatus.active:
            raise StateConflictError("Timeout is allowed only for active participants")
        if model.current_position != position:
            raise StateConflictError("Timeout is allowed only for the active player")
        if not timer_expired:
            raise StateConflictError("Current turn has not expired yet")

    def hand_can_act(self, player: PlayerSlotSnapshot) -> bool:
        if player.participant_status != ParticipantStatus.active:
            return False
        cards = player.cards
        score, blackjack = self.score_fn(cards)
        return not blackjack and score < 21

    def first_playable_position(self, players: list[PlayerSlotSnapshot]) -> Optional[int]:
        for player in players:
            if self.hand_can_act(player):
                return player.position
        return None

    def next_playable_position(self, players: list[PlayerSlotSnapshot], current_position: Optional[int]) -> Optional[int]:
        if current_position is None:
            return self.first_playable_position(players)
        for player in players:
            if player.position <= current_position:
                continue
            if self.hand_can_act(player):
                return player.position
        return None

    def keeps_same_turn(self, action: str, projected_score: int) -> bool:
        return action == "hit" and projected_score < 21

    def advances_to_next_player(self, action: str, projected_score: int, next_position: Optional[int]) -> bool:
        if next_position is None:
            return False
        if action == "hit":
            return projected_score >= 21
        return action in {"stand", "double", "timeout"}

    def advances_to_dealer(self, action: str, projected_score: int, next_position: Optional[int]) -> bool:
        if next_position is not None:
            return False
        if action == "hit":
            return projected_score >= 21
        return action in {"stand", "double", "timeout"}
