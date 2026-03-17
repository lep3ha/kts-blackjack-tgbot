"""Accessor for player/deck/session CRUD operations."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.errors import BadRequestError, GameLogicError, NotFoundError
from app.models import ChatMode, Deck, GameSession, ParticipantStatus, Player, PlayerToSession
from app.schemas import DeckCreateRequest, PlayerCreateRequest, SeatCreateRequest, SessionCreateRequest


class CatalogAccessor:
    """Encapsulates DB operations unrelated to active blackjack round flow."""

    async def create_player(self, payload: PlayerCreateRequest) -> dict:
        async for db in get_db():
            player = Player(
                telegram_id=payload.telegram_id,
                username=payload.username,
                first_name=payload.first_name,
                bank=payload.bank,
            )
            db.add(player)
            try:
                await db.commit()
            except IntegrityError as exc:
                await db.rollback()
                raise BadRequestError("Player with this telegram_id already exists") from exc
            await db.refresh(player)
            return {
                "id": player.id,
                "telegram_id": player.telegram_id,
                "username": player.username,
                "first_name": player.first_name,
                "bank": player.bank,
            }
        raise RuntimeError("Database session is unavailable")

    async def create_deck(self, payload: DeckCreateRequest) -> dict:
        async for db in get_db():
            deck = Deck(chat_id=payload.chat_id, meta=payload.meta)
            db.add(deck)
            try:
                await db.commit()
            except IntegrityError as exc:
                await db.rollback()
                raise BadRequestError("Deck with this chat_id already exists") from exc
            await db.refresh(deck)
            return {"id": deck.id, "chat_id": deck.chat_id, "meta": deck.meta}
        raise RuntimeError("Database session is unavailable")

    async def create_session(self, payload: SessionCreateRequest) -> dict:
        async for db in get_db():
            deck_result = await db.execute(select(Deck).where(Deck.id == payload.deck_id))
            deck = deck_result.scalar_one_or_none()
            if deck is None:
                raise NotFoundError("Deck not found")

            session = GameSession(
                deck_id=payload.deck_id,
                count_players=payload.count_players,
                chat_mode=ChatMode.group,
            )
            db.add(session)
            try:
                await db.commit()
            except IntegrityError as exc:
                await db.rollback()
                raise BadRequestError("Deck already has an unfinished session") from exc
            await db.refresh(session)
            return {
                "id": session.id,
                "deck_id": session.deck_id,
                "status": session.status.value,
                "count_players": session.count_players,
            }
        raise RuntimeError("Database session is unavailable")

    async def seat_player(self, session_id: int, payload: SeatCreateRequest) -> dict:
        async for db in get_db():
            session_result = await db.execute(select(GameSession).where(GameSession.id == session_id))
            session = session_result.scalar_one_or_none()
            if session is None:
                raise NotFoundError("Session not found")

            player_result = await db.execute(select(Player).where(Player.id == payload.player_id))
            player = player_result.scalar_one_or_none()
            if player is None:
                raise NotFoundError("Player not found")

            if player.bank < payload.bet:
                raise GameLogicError("Insufficient player bank for the bet")

            seat = PlayerToSession(
                session_id=session_id,
                player_id=payload.player_id,
                position=payload.position,
                participant_status=ParticipantStatus.joined,
                bet=payload.bet,
                cards=[],
            )
            db.add(seat)
            try:
                await db.commit()
            except IntegrityError as exc:
                await db.rollback()
                raise BadRequestError("Seat is already taken or player already joined") from exc

            return {
                "session_id": session_id,
                "player_id": payload.player_id,
                "position": payload.position,
                "bet": payload.bet,
            }
        raise RuntimeError("Database session is unavailable")
