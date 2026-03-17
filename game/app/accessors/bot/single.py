"""Single-chat specific bot flows."""
from __future__ import annotations

from app.errors import AuthorizationError, GameLogicError, NotFoundError, StateConflictError
from app.models import ChatMode, GameSession, ParticipantStatus, PlayerToSession, SessionStatus
from app.schemas import SingleSessionStartRequest, SingleSessionStopRequest
from app.services.blackjack_service import BlackjackService


class SingleBotMixin:
    async def start_single_session(self, payload: SingleSessionStartRequest) -> dict:
        self._ensure_single_chat(payload.chat_type)

        async for db in self._iter_db():
            player = await self._get_player_by_telegram_id(db, payload.actor_telegram_id)
            if player is None:
                raise NotFoundError("Player not found")
            if player.is_banned:
                raise AuthorizationError("Player is banned")
            self._apply_player_profile(
                player,
                username=payload.actor_username,
                first_name=payload.actor_first_name,
            )
            if player.bank < payload.bet:
                raise GameLogicError("Insufficient player bank for the bet")

            await self._ensure_player_has_no_unfinished_session(db, player.id)

            existing_session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id)
            if existing_session is not None:
                raise StateConflictError("Chat already has an unfinished session")

            deck = await self._get_or_create_deck(db, payload.chat_id)
            session = GameSession(
                deck_id=deck.id,
                status=SessionStatus.lobby_open,
                chat_mode=ChatMode.single,
                count_players=1,
            )
            db.add(session)
            await db.flush()

            db.add(
                PlayerToSession(
                    player_id=player.id,
                    session_id=session.id,
                    position=1,
                    participant_status=ParticipantStatus.joined,
                    bet=payload.bet,
                    cards=[],
                )
            )

            try:
                machine = await BlackjackService.load(db, session.id)
                await machine.start_session()
            except Exception:
                await db.rollback()
                raise

            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")

    async def stop_single_session(self, payload: SingleSessionStopRequest) -> dict:
        self._ensure_single_chat(payload.chat_type)

        async for db in self._iter_db():
            await self._sync_actor_profile(
                db,
                telegram_id=payload.actor_telegram_id,
                username=payload.actor_username,
                first_name=payload.actor_first_name,
            )
            session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id, chat_mode=ChatMode.single)
            if session is None:
                raise NotFoundError("Active single session not found")
            if session.chat_mode != ChatMode.single or session.status != SessionStatus.in_progress:
                raise StateConflictError("Single session is not in progress")

            machine = await BlackjackService.load(db, session.id)
            seat = await self._get_machine_player_by_telegram_id(db, machine, payload.actor_telegram_id)
            if seat is None:
                raise NotFoundError("Player is not part of the session")
            if seat.participant_status != ParticipantStatus.active:
                raise StateConflictError("Only active participants can stop the single session")

            await machine.apply_action(seat.position, "stand")
            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")
