"""State machine settings that are not part of persistence model."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class BlackjackStateMachineSettings:
    """Feature and behavior flags for blackjack runtime rules."""

    player_actions: frozenset[str] = field(default_factory=lambda: frozenset({"hit", "stand", "double"}))
    dealer_stand_score: int = 17
