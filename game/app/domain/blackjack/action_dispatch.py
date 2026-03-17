"""Dispatch player actions to persistence-ready decisions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.errors import BadRequestError


@dataclass(slots=True)
class ActionRuntimeContext:
    position: int
    action: str
    seat: Any
    target_state_id: str
    drawn_card: Optional[str]
    projected_cards: list[str]
    projected_score: int
    next_position: Optional[int]


@dataclass(slots=True)
class ActionDispatchResult:
    cards: list[str]
    bet: int
    next_position: Optional[int]
    should_schedule_timer: bool
    details: dict[str, Any]


class PlayerActionDispatcher:
    """Converts player action context into repository payload."""

    def dispatch(self, ctx: ActionRuntimeContext) -> ActionDispatchResult:
        handler = {
            "hit": self._handle_hit,
            "stand": self._handle_stand,
            "double": self._handle_double,
        }.get(ctx.action)

        if handler is None:
            raise BadRequestError(f"Unsupported player action: {ctx.action}")
        return handler(ctx)

    def _base(self, ctx: ActionRuntimeContext) -> tuple[bool, Optional[int], dict[str, Any]]:
        keep_same_player = ctx.target_state_id == "player_turn" and ctx.action == "hit" and ctx.projected_score < 21
        next_position = ctx.position if keep_same_player else ctx.next_position

        details: dict[str, Any] = {"actor": "player"}
        if ctx.drawn_card is not None:
            details["card"] = ctx.drawn_card

        move_to_next_player = ctx.target_state_id == "player_turn" and not keep_same_player
        if move_to_next_player:
            details["next_position"] = next_position

        return keep_same_player, next_position, details

    def _handle_hit(self, ctx: ActionRuntimeContext) -> ActionDispatchResult:
        _, next_position, details = self._base(ctx)
        return ActionDispatchResult(
            cards=list(ctx.projected_cards),
            bet=ctx.seat.bet,
            next_position=next_position,
            should_schedule_timer=ctx.target_state_id == "player_turn",
            details=details,
        )

    def _handle_stand(self, ctx: ActionRuntimeContext) -> ActionDispatchResult:
        _, next_position, details = self._base(ctx)
        return ActionDispatchResult(
            cards=list(ctx.seat.cards),
            bet=ctx.seat.bet,
            next_position=next_position,
            should_schedule_timer=ctx.target_state_id == "player_turn",
            details=details,
        )

    def _handle_double(self, ctx: ActionRuntimeContext) -> ActionDispatchResult:
        _, next_position, details = self._base(ctx)
        new_bet = ctx.seat.bet * 2
        details["new_bet"] = new_bet
        return ActionDispatchResult(
            cards=list(ctx.projected_cards),
            bet=new_bet,
            next_position=next_position,
            should_schedule_timer=ctx.target_state_id == "player_turn",
            details=details,
        )
