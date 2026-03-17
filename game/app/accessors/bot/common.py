"""Common bot accessor behavior shared across chat modes."""
from __future__ import annotations

from datetime import timedelta
from typing import AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now_naive
from app.db import get_db
from app.errors import (
    BadRequestError,
    NotFoundError,
    StaleTurnError,
    StateConflictError,
)
from app.models import ChatMode, Deck, GameSession, ParticipantStatus, Player, PlayerToSession, SessionStatus, State
from app.schemas import BotActionRequest, BotSessionQueryRequest, BotTimeoutRequest
from app.services.blackjack_service import BlackjackService


class CommonBotMixin:
    def __init__(self, *, include_legacy_fields: bool = True) -> None:
        self._include_legacy_fields = include_legacy_fields

    def _iter_db(self) -> AsyncIterator[AsyncSession]:
        return get_db()

    def _utc_now_naive(self):
        return utc_now_naive()

    async def apply_action(self, payload: BotActionRequest) -> dict:
        chat_mode = self._chat_mode_from_type(payload.chat_type)

        async for db in self._iter_db():
            await self._sync_actor_profile(
                db,
                telegram_id=payload.actor_telegram_id,
                username=payload.actor_username,
                first_name=payload.actor_first_name,
            )
            session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id, chat_mode=chat_mode)
            if session is None:
                raise NotFoundError("Active session not found")
            if session.status != SessionStatus.in_progress:
                raise StateConflictError("Session is not in progress")

            machine = await BlackjackService.load(db, session.id)
            if payload.turn_version != machine.model.turn_version:
                raise StaleTurnError("Turn version is stale for action request")
            seat = await self._get_machine_player_by_telegram_id(db, machine, payload.actor_telegram_id)
            if seat is None:
                raise NotFoundError("Player is not part of the session")
            if seat.participant_status != ParticipantStatus.active:
                raise StateConflictError("Only active participants can make actions")
            if machine.model.current_position != seat.position:
                raise StateConflictError("Actor is not the current active player")

            context = await machine.apply_action(seat.position, payload.action)
            return await self._build_session_snapshot(db, context.session_id)

        raise RuntimeError("Database session is unavailable")

    async def apply_timeout(self, payload: BotTimeoutRequest) -> dict:
        chat_mode = self._chat_mode_from_type(payload.chat_type)

        async for db in self._iter_db():
            session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id, chat_mode=chat_mode)
            if session is None:
                raise NotFoundError("Active session not found")
            if session.status != SessionStatus.in_progress:
                raise StateConflictError("Session is not in progress")

            machine = await BlackjackService.load(db, session.id)
            if payload.turn_version != machine.model.turn_version:
                raise StaleTurnError("Turn version is stale for timeout request")
            if machine.model.current_position is None:
                raise StateConflictError("Session has no active turn")

            seat = machine.model.player_by_position(machine.model.current_position)
            if seat is None:
                raise StateConflictError("Current active player not found")

            if seat.participant_status in {ParticipantStatus.inactive, ParticipantStatus.settled}:
                return await self._build_session_snapshot(db, session.id)

            context = await machine.handle_timeout(seat.position)
            return await self._build_session_snapshot(db, context.session_id)

        raise RuntimeError("Database session is unavailable")

    async def get_current_session(self, payload: BotSessionQueryRequest) -> dict:
        chat_mode = self._chat_mode_from_type(payload.chat_type)

        async for db in self._iter_db():
            session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id, chat_mode=chat_mode)
            if session is None:
                raise NotFoundError("Current session not found")
            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")

    async def get_last_session(self, payload: BotSessionQueryRequest) -> dict:
        chat_mode = self._chat_mode_from_type(payload.chat_type)

        async for db in self._iter_db():
            session = await self._get_last_closed_session_by_chat_id(db, payload.chat_id, chat_mode=chat_mode)
            if session is None:
                raise NotFoundError("Last completed session not found")
            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")

    def _ensure_group_chat(self, chat_type: str) -> None:
        if chat_type != "group":
            raise BadRequestError("This endpoint supports only group chats")

    def _ensure_single_chat(self, chat_type: str) -> None:
        if chat_type != "single":
            raise BadRequestError("This endpoint supports only single chats")

    def _chat_mode_from_type(self, chat_type: str) -> ChatMode:
        if chat_type == "group":
            return ChatMode.group
        if chat_type == "single":
            return ChatMode.single
        raise BadRequestError("Unsupported chat type")

    async def _get_player_by_username(self, db: AsyncSession, username: str) -> Player | None:
        result = await db.execute(select(Player).where(Player.username == username))
        return result.scalar_one_or_none()

    async def _get_player_by_telegram_id(self, db: AsyncSession, telegram_id: str) -> Player | None:
        result = await db.execute(select(Player).where(Player.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def _sync_actor_profile(
        self,
        db: AsyncSession,
        *,
        telegram_id: str,
        username: str | None,
        first_name: str | None,
    ) -> None:
        if username is None and first_name is None:
            return
        player = await self._get_player_by_telegram_id(db, telegram_id)
        self._apply_player_profile(player, username=username, first_name=first_name)

    @staticmethod
    def _apply_player_profile(player: Player | None, *, username: str | None, first_name: str | None) -> None:
        if player is None:
            return
        if username is not None:
            player.username = username
        if first_name is not None:
            player.first_name = first_name

    async def _get_or_create_deck(self, db: AsyncSession, chat_id: str) -> Deck:
        result = await db.execute(select(Deck).where(Deck.chat_id == chat_id))
        deck = result.scalar_one_or_none()
        if deck is not None:
            return deck

        deck = Deck(chat_id=chat_id, meta={})
        db.add(deck)
        await db.flush()
        return deck

    async def _get_unfinished_session_by_chat_id(
        self,
        db: AsyncSession,
        chat_id: str,
        *,
        chat_mode: ChatMode | None = None,
    ) -> GameSession | None:
        query = (
            select(GameSession)
            .join(Deck, Deck.id == GameSession.deck_id)
            .where(Deck.chat_id == chat_id, GameSession.status != SessionStatus.closed)
            .order_by(GameSession.id.desc())
        )
        if chat_mode is not None:
            query = query.where(GameSession.chat_mode == chat_mode)
        result = await db.execute(query)
        return result.scalars().first()

    async def _get_last_closed_session_by_chat_id(
        self,
        db: AsyncSession,
        chat_id: str,
        *,
        chat_mode: ChatMode | None = None,
    ) -> GameSession | None:
        query = (
            select(GameSession)
            .join(Deck, Deck.id == GameSession.deck_id)
            .where(Deck.chat_id == chat_id, GameSession.status == SessionStatus.closed)
            .order_by(GameSession.id.desc())
        )
        if chat_mode is not None:
            query = query.where(GameSession.chat_mode == chat_mode)
        result = await db.execute(query)
        return result.scalars().first()

    async def _ensure_player_has_no_unfinished_session(self, db: AsyncSession, player_id: int) -> None:
        result = await db.execute(
            select(GameSession.id)
            .join(PlayerToSession, PlayerToSession.session_id == GameSession.id)
            .where(PlayerToSession.player_id == player_id, GameSession.status != SessionStatus.closed)
            .limit(1)
        )
        existing_session_id = result.scalar_one_or_none()
        if existing_session_id is not None:
            raise StateConflictError("Player already participates in an unfinished session")

    async def _next_free_position(self, db: AsyncSession, session_id: int) -> int:
        result = await db.execute(select(func.max(PlayerToSession.position)).where(PlayerToSession.session_id == session_id))
        max_position = result.scalar_one_or_none() or 0
        return int(max_position) + 1

    async def _get_session_participants(self, db: AsyncSession, session_id: int):
        result = await db.execute(
            select(PlayerToSession, Player)
            .join(Player, Player.id == PlayerToSession.player_id)
            .where(PlayerToSession.session_id == session_id)
            .order_by(PlayerToSession.position)
        )
        return result.all()

    async def _get_machine_player_by_telegram_id(self, db: AsyncSession, machine: BlackjackService, telegram_id: str):
        player = await self._get_player_by_telegram_id(db, telegram_id)
        if player is None:
            return None
        for seat in machine.model.players:
            if seat.player_id == player.id:
                return seat
        return None

    async def _get_result_map(self, db: AsyncSession, session_id: int) -> dict[int, dict[str, int | str]]:
        result = await db.execute(
            select(State.position, State.details)
            .where(State.session_id == session_id, State.action == "result")
            .order_by(State.id)
        )
        payload: dict[int, dict[str, int | str]] = {}
        for position, details in result.all():
            payload[position] = {
                "result": details.get("result"),
                "delta": details.get("delta"),
            }
        return payload
