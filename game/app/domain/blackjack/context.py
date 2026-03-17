"""Domain-level context and snapshot types.

These dataclasses represent the in-memory model that the state machine operates on.
They are intentionally independent from service/repository implementation details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.models import ChatMode, ParticipantStatus, SessionStatus


@dataclass(slots=True)
class PlayerSlotSnapshot:
    player_to_session_id: int
    player_id: int
    position: int
    bet: int
    participant_status: ParticipantStatus = ParticipantStatus.active
    cards: list[str] = field(default_factory=list)
    bank: int = 0


@dataclass(slots=True)
class BlackjackSessionContext:
    session_id: int
    deck_id: int
    status: SessionStatus
    state: str
    chat_mode: ChatMode = ChatMode.group
    turn_version: int = 0
    dealer_cards: list[str] = field(default_factory=list)
    current_position: Optional[int] = None
    current_timer: Optional[datetime] = None
    count_players: int = 0
    players: list[PlayerSlotSnapshot] = field(default_factory=list)
    turn_timeout_seconds: int = 30

    def player_by_position(self, position: Optional[int]) -> Optional[PlayerSlotSnapshot]:
        if position is None:
            return None
        for player in self.players:
            if player.position == position:
                return player
        return None

    def first_position(self) -> Optional[int]:
        if not self.players:
            return None
        return min(player.position for player in self.players)
