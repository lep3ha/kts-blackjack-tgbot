"""Accessor for active blackjack round operations."""
from __future__ import annotations

from app.db import get_db
from app.schemas import ActionRequest, SessionStateResponse, TimeoutRequest
from app.services.blackjack_service import BlackjackService


class BlackjackAccessor:
    """Encapsulates DB-backed interactions with the blackjack state machine."""

    @staticmethod
    def _context_to_response(context, *, available_moves: list[str]) -> SessionStateResponse:
        return SessionStateResponse(
            session_id=context.session_id,
            deck_id=context.deck_id,
            status=context.status.value,
            state=context.state,
            available_moves=list(available_moves),
            current_position=context.current_position,
            current_timer=context.current_timer,
            dealer_cards=list(context.dealer_cards),
            players=[
                {
                    "player_id": player.player_id,
                    "position": player.position,
                    "bet": player.bet,
                    "cards": list(player.cards),
                    "bank": player.bank,
                }
                for player in context.players
            ],
        )

    async def start_session(self, session_id: int) -> dict:
        async for db in get_db():
            machine = await BlackjackService.load(db, session_id)
            context = await machine.start_session()
            return self._context_to_response(context, available_moves=machine.available_moves()).model_dump()
        raise RuntimeError("Database session is unavailable")

    async def make_action(self, session_id: int, payload: ActionRequest) -> dict:
        async for db in get_db():
            machine = await BlackjackService.load(db, session_id)
            context = await machine.apply_action(payload.position, payload.action)
            return self._context_to_response(context, available_moves=machine.available_moves()).model_dump()
        raise RuntimeError("Database session is unavailable")

    async def force_timeout(self, session_id: int, payload: TimeoutRequest) -> dict:
        async for db in get_db():
            machine = await BlackjackService.load(db, session_id)
            context = await machine.handle_timeout(payload.position)
            return self._context_to_response(context, available_moves=machine.available_moves()).model_dump()
        raise RuntimeError("Database session is unavailable")

    async def get_session_state(self, session_id: int) -> dict:
        async for db in get_db():
            machine = await BlackjackService.load(db, session_id, for_update=False)
            return self._context_to_response(machine.model, available_moves=machine.available_moves()).model_dump()
        raise RuntimeError("Database session is unavailable")
