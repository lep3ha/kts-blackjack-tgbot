"""Snapshot building logic for bot-facing responses."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models import ChatMode, Deck, GameSession, Player, PlayerHand, SessionStatus
from app.schemas import GroupSessionSnapshotCanonicalResponse, GroupSessionSnapshotResponse
from app.services.blackjack_service import BlackjackService

_DEALER_REVEAL_STATES: frozenset[str] = frozenset({"dealer_turn", "resolving", "closed"})


class SnapshotBotMixin:
    @staticmethod
    def _resolve_display_name(player: Player) -> str:
        if player.username:
            return player.username
        if player.first_name:
            return player.first_name
        return player.telegram_id

    async def _build_session_snapshot(self, db: AsyncSession, session_id: int) -> dict:
        session_result = await db.execute(
            select(GameSession, Deck)
            .join(Deck, Deck.id == GameSession.deck_id)
            .where(GameSession.id == session_id)
        )
        session_row = session_result.one_or_none()
        if session_row is None:
            raise NotFoundError("Session not found")

        session, deck = session_row
        participants = await self._get_session_participants(db, session.id)
        result_map = await self._get_result_map(db, session.id)
        available_moves: list[str] = []
        runtime_state = self._derive_runtime_state(session.status)

        if session.status == SessionStatus.in_progress:
            machine = await BlackjackService.load(db, session.id, for_update=False)
            available_moves = machine.available_moves()
            runtime_state = machine.model.state

        can_start = session.status == SessionStatus.lobby_open and len(participants) > 0
        start_error = None
        if session.status == SessionStatus.lobby_open and not participants:
            start_error = "Lobby has no joined participants"
        elif session.status != SessionStatus.lobby_open:
            start_error = "Session is not in lobby_open state"

        is_revealed = runtime_state in _DEALER_REVEAL_STATES
        dealer_cards_raw = list(session.dealer_cards or [])
        visible_dealer_cards = (
            dealer_cards_raw
            if is_revealed or len(dealer_cards_raw) <= 1
            else [dealer_cards_raw[0], "?"]
        )

        lobby = None
        if session.chat_mode == ChatMode.group and session.status == SessionStatus.lobby_open:
            lobby = {
                "count_players": session.count_players,
                "participants_count": len(participants),
                "can_start": can_start,
                "start_error": start_error,
            }

        summary = None
        if session.status == SessionStatus.closed:
            deltas = [entry.get("delta") for entry in result_map.values()]
            numeric_deltas = [delta for delta in deltas if isinstance(delta, int)]
            summary = {
                "participants_count": len(participants),
                "results_count": len(numeric_deltas),
                "total_delta": sum(numeric_deltas) if numeric_deltas else 0,
            }

        position_to_telegram_id = {seat.position: player.telegram_id for seat, player in participants}
        position_to_player = {seat.position: player for seat, player in participants}
        hands_by_seat_id = await self._get_hands_by_seat_id(db, participants)
        current_player = None
        if session.current_position is not None:
            telegram_id = position_to_telegram_id.get(session.current_position)
            player = position_to_player.get(session.current_position)
            if telegram_id is not None:
                current_player = {
                    "telegram_id": telegram_id,
                    "position": session.current_position,
                    "hand_index": session.current_hand_index,
                    "username": player.username if player else None,
                    "first_name": player.first_name if player else None,
                    "display_name": self._resolve_display_name(player) if player else None,
                }

        base_payload = dict(
            chat_id=deck.chat_id,
            chat_mode=session.chat_mode.value,
            session_id=session.id,
            session_status=session.status.value,
            runtime_state=runtime_state,
            turn_version=session.turn_version,
            current_player=current_player,
            dealer={
                "cards": visible_dealer_cards,
                "is_final": session.status == SessionStatus.closed,
                "is_revealed": is_revealed,
            },
            lobby=lobby,
            summary=summary,
            available_moves=available_moves,
            current_hand_index=session.current_hand_index,
            current_timer=session.current_timer,
            participants=[
                {
                    "telegram_id": player.telegram_id,
                    "username": player.username,
                    "first_name": player.first_name,
                    "display_name": self._resolve_display_name(player),
                    "player_id": player.id,
                    "position": seat.position,
                    "participant_status": seat.participant_status.value,
                    "bet": seat.bet,
                    "cards": list(seat.cards or []),
                    "bank": player.bank,
                    "insurance_bet": int(seat.insurance_bet or 0),
                    "result": result_map.get(seat.position, {}).get("result"),
                    "delta": result_map.get(seat.position, {}).get("delta"),
                    "insurance_delta": result_map.get(seat.position, {}).get("insurance_delta", 0),
                    "hand_settlements": result_map.get(seat.position, {}).get("hand_settlements") or [],
                    "hands": hands_by_seat_id.get(seat.id)
                    or [
                        {
                            "hand_index": 0,
                            "cards": list(seat.cards or []),
                            "bet": seat.bet,
                            "participant_status": seat.participant_status.value,
                        }
                    ],
                }
                for seat, player in participants
            ],
        )

        if self._include_legacy_fields:
            response = GroupSessionSnapshotResponse(
                **base_payload,
                current_position=session.current_position,
                dealer_cards=visible_dealer_cards,
                can_start=can_start,
                start_error=start_error,
            )
        else:
            response = GroupSessionSnapshotCanonicalResponse(**base_payload)

        return response.model_dump(mode="json")

    def _derive_runtime_state(self, status: SessionStatus) -> str:
        if status == SessionStatus.lobby_open:
            return "waiting"
        if status == SessionStatus.in_progress:
            return "player_turn"
        return "closed"

    async def _get_hands_by_seat_id(self, db: AsyncSession, participants) -> dict[int, list[dict[str, int | str | list[str]]]]:
        seat_ids = [seat.id for seat, _ in participants]
        if not seat_ids:
            return {}

        hands_result = await db.execute(
            select(PlayerHand)
            .where(PlayerHand.player_to_session_id.in_(seat_ids))
            .order_by(PlayerHand.player_to_session_id, PlayerHand.hand_index)
        )
        payload: dict[int, list[dict[str, int | str | list[str]]]] = {}
        for hand in hands_result.scalars().all():
            payload.setdefault(hand.player_to_session_id, []).append(
                {
                    "hand_index": hand.hand_index,
                    "cards": list(hand.cards or []),
                    "bet": hand.bet,
                    "participant_status": hand.participant_status.value,
                }
            )
        return payload
