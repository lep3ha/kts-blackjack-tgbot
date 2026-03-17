"""Bot-facing accessor for chat-based blackjack scenarios."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now_naive
from app.db import get_db
from app.errors import (
    AuthorizationError,
    BadRequestError,
    GameLogicError,
    NotFoundError,
    StaleTurnError,
    StateConflictError,
)
from app.models import ChatMode, Deck, GameSession, ParticipantStatus, Player, PlayerToSession, SessionStatus, State
from app.schemas import (
    AdminBanRequest,
    AdminTopupRequest,
    BotActionRequest,
    BotSessionQueryRequest,
    BotTimeoutRequest,
    GroupPlayerStopRequest,
    GroupLobbyJoinRequest,
    GroupLobbyOpenRequest,
    GroupLobbyQueryRequest,
    GroupLobbyStartRequest,
    GroupSessionSnapshotCanonicalResponse,
    GroupSessionSnapshotResponse,
    SingleSessionStopRequest,
    SingleSessionStartRequest,
)
from app.services.blackjack_service import BlackjackService

_DEALER_REVEAL_STATES: frozenset[str] = frozenset({"dealer_turn", "resolving", "closed"})


class BotGameAccessor:
    """Encapsulates bot-facing chat flows that do not rely on session ids."""

    def __init__(self, *, include_legacy_fields: bool = True) -> None:
        self._include_legacy_fields = include_legacy_fields

    async def apply_action(self, payload: BotActionRequest) -> dict:
        chat_mode = self._chat_mode_from_type(payload.chat_type)

        async for db in get_db():
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

        async for db in get_db():
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

            # Controlled no-op for outdated timeout workers targeting already inactive/settled hands.
            if seat.participant_status in {ParticipantStatus.inactive, ParticipantStatus.settled}:
                return await self._build_session_snapshot(db, session.id)

            context = await machine.handle_timeout(seat.position)
            return await self._build_session_snapshot(db, context.session_id)

        raise RuntimeError("Database session is unavailable")

    async def get_current_session(self, payload: BotSessionQueryRequest) -> dict:
        chat_mode = self._chat_mode_from_type(payload.chat_type)

        async for db in get_db():
            session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id, chat_mode=chat_mode)
            if session is None:
                raise NotFoundError("Current session not found")
            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")

    async def get_last_session(self, payload: BotSessionQueryRequest) -> dict:
        chat_mode = self._chat_mode_from_type(payload.chat_type)

        async for db in get_db():
            session = await self._get_last_closed_session_by_chat_id(db, payload.chat_id, chat_mode=chat_mode)
            if session is None:
                raise NotFoundError("Last completed session not found")
            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")

    async def start_single_session(self, payload: SingleSessionStartRequest) -> dict:
        self._ensure_single_chat(payload.chat_type)

        async for db in get_db():
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

    async def stop_group_player(self, payload: GroupPlayerStopRequest) -> dict:
        self._ensure_group_chat(payload.chat_type)

        async for db in get_db():
            await self._sync_actor_profile(
                db,
                telegram_id=payload.actor_telegram_id,
                username=payload.actor_username,
                first_name=payload.actor_first_name,
            )
            session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id, chat_mode=ChatMode.group)
            if session is None:
                raise NotFoundError("Active group session not found")
            if session.chat_mode != ChatMode.group or session.status != SessionStatus.in_progress:
                raise StateConflictError("Group session is not in progress")

            machine = await BlackjackService.load(db, session.id)
            seat = await self._get_machine_player_by_telegram_id(db, machine, payload.actor_telegram_id)
            if seat is None:
                raise NotFoundError("Player is not part of the session")
            if seat.participant_status != ParticipantStatus.active:
                raise StateConflictError("Only active participants can stop themselves")

            settlement = machine.settlement_policy.build_settlements([seat], machine.model.dealer_cards)[0]
            seat.participant_status = ParticipantStatus.inactive

            next_position = machine.model.current_position
            next_timer = machine.model.current_timer
            if machine.model.current_position == seat.position:
                next_position = machine.turn_rules.next_playable_position(machine.model.players, seat.position)
                if next_position is None:
                    next_timer = None
                else:
                    next_timer = utc_now_naive() + timedelta(seconds=machine.model.turn_timeout_seconds)

            remaining_active = [
                player for player in machine.model.players if player.position != seat.position and player.participant_status == ParticipantStatus.active
            ]

            await machine.repository.persist_partial_settlement(
                machine.model,
                position=seat.position,
                participant_status=ParticipantStatus.inactive,
                settlement=settlement,
                next_position=next_position,
                next_timer=next_timer,
                close_session=not remaining_active,
            )

            if remaining_active and next_position is None:
                await machine.repository.persist_turn_assignment(
                    machine.model,
                    position=None,
                    timer=None,
                    action="players_done",
                    details={"actor": "system", "reason": "player_stop"},
                )
                await machine.run_dealer_turn()
                await machine.settle_round()

            await machine.repository.commit()
            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")

    async def stop_single_session(self, payload: SingleSessionStopRequest) -> dict:
        self._ensure_single_chat(payload.chat_type)

        async for db in get_db():
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

            # single_stop should behave as if player clicked Stand.
            await machine.apply_action(seat.position, "stand")
            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")

    async def open_group_lobby(self, payload: GroupLobbyOpenRequest) -> dict:
        self._ensure_group_chat(payload.chat_type)
        if not payload.actor_is_admin:
            raise AuthorizationError("Only chat admins can open a group lobby")

        async for db in get_db():
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
            deck = await self._get_or_create_deck(db, payload.chat_id)

            existing_session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id, chat_mode=ChatMode.group)
            if existing_session is not None:
                raise StateConflictError("Chat already has an unfinished session")

            session = GameSession(
                deck_id=deck.id,
                status=SessionStatus.lobby_open,
                chat_mode=ChatMode.group,
                count_players=payload.count_players,
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
                await db.commit()
            except IntegrityError as exc:
                await db.rollback()
                raise StateConflictError("Unable to open lobby because chat state changed") from exc

            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")

    async def join_group_lobby(self, payload: GroupLobbyJoinRequest) -> dict:
        self._ensure_group_chat(payload.chat_type)

        async for db in get_db():
            session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id, chat_mode=ChatMode.group)
            if session is None:
                raise NotFoundError("Group lobby not found")
            if session.status != SessionStatus.lobby_open:
                raise StateConflictError("Group lobby is not open")

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
            next_position = await self._next_free_position(db, session.id)
            if next_position > session.count_players:
                raise StateConflictError("Group lobby is full")

            db.add(
                PlayerToSession(
                    player_id=player.id,
                    session_id=session.id,
                    position=next_position,
                    participant_status=ParticipantStatus.joined,
                    bet=payload.bet,
                    cards=[],
                )
            )

            try:
                await db.commit()
            except IntegrityError as exc:
                await db.rollback()
                raise StateConflictError("Unable to join lobby because player state changed") from exc

            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")

    async def get_group_lobby(self, payload: GroupLobbyQueryRequest) -> dict:
        async for db in get_db():
            session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id, chat_mode=ChatMode.group)
            if session is None:
                raise NotFoundError("Group lobby not found")
            if session.status != SessionStatus.lobby_open:
                raise StateConflictError("Group lobby is not open")
            return await self._build_session_snapshot(db, session.id)

        raise RuntimeError("Database session is unavailable")

    async def start_group_lobby(self, payload: GroupLobbyStartRequest) -> dict:
        self._ensure_group_chat(payload.chat_type)
        if not payload.actor_is_admin:
            raise AuthorizationError("Only chat admins can start a group lobby")

        async for db in get_db():
            await self._sync_actor_profile(
                db,
                telegram_id=payload.actor_telegram_id,
                username=payload.actor_username,
                first_name=payload.actor_first_name,
            )
            session = await self._get_unfinished_session_by_chat_id(db, payload.chat_id, chat_mode=ChatMode.group)
            if session is None:
                raise NotFoundError("Group lobby not found")
            if session.status != SessionStatus.lobby_open:
                raise StateConflictError("Group lobby is not open")

            participants = await self._get_session_participants(db, session.id)
            if not participants:
                raise StateConflictError("Lobby has no joined participants")

            for participant in participants:
                if participant[1].bank < participant[0].bet:
                    raise GameLogicError("All lobby participants must have sufficient bank for the bet")

            machine = await BlackjackService.load(db, session.id)
            await machine.start_session()
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

    async def admin_topup(self, payload: AdminTopupRequest) -> dict:
        async for db in get_db():
            player = await self._get_player_by_identifier(db, payload.username)
            if player is None:
                raise NotFoundError(f"Player '{payload.username}' not found")
            player.bank += payload.amount
            await db.commit()
            return {"username": player.username or player.telegram_id, "new_bank": player.bank}
        raise RuntimeError("Database session is unavailable")

    async def admin_ban(self, payload: AdminBanRequest) -> dict:
        async for db in get_db():
            player = await self._get_player_by_identifier(db, payload.username)
            if player is None:
                raise NotFoundError(f"Player '{payload.username}' not found")
            player.is_banned = True
            await db.commit()
            return {"username": player.username or player.telegram_id, "is_banned": player.is_banned}
        raise RuntimeError("Database session is unavailable")

    async def _get_player_by_identifier(self, db: AsyncSession, identifier: str) -> Player | None:
        """Get player by username or telegram_id. Tries username first, then falls back to telegram_id."""
        # Try by username first
        result = await db.execute(select(Player).where(Player.username == identifier))
        player = result.scalar_one_or_none()
        if player is not None:
            return player
        
        # Fall back to telegram_id
        result = await db.execute(select(Player).where(Player.telegram_id == identifier))
        return result.scalar_one_or_none()

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

    @staticmethod
    def _resolve_display_name(player: Player) -> str:
        if player.username:
            return player.username
        if player.first_name:
            return player.first_name
        return player.telegram_id

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
        result = await db.execute(
            select(func.max(PlayerToSession.position)).where(PlayerToSession.session_id == session_id)
        )
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
        current_player = None
        if session.current_position is not None:
            telegram_id = position_to_telegram_id.get(session.current_position)
            if telegram_id is not None:
                current_player = {
                    "telegram_id": telegram_id,
                    "position": session.current_position,
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
                    "result": result_map.get(seat.position, {}).get("result"),
                    "delta": result_map.get(seat.position, {}).get("delta"),
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