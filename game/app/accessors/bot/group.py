"""Group-chat specific bot flows."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from app.errors import AuthorizationError, GameLogicError, NotFoundError, StateConflictError
from app.models import ChatMode, GameSession, ParticipantStatus, PlayerToSession, SessionStatus
from app.schemas import GroupLobbyJoinRequest, GroupLobbyOpenRequest, GroupLobbyQueryRequest, GroupLobbyStartRequest, GroupPlayerStopRequest
from app.services.blackjack_service import BlackjackService


class GroupBotMixin:
    async def stop_group_player(self, payload: GroupPlayerStopRequest) -> dict:
        self._ensure_group_chat(payload.chat_type)

        async for db in self._iter_db():
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
                    next_timer = self._utc_now_naive() + timedelta(seconds=machine.model.turn_timeout_seconds)

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

    async def open_group_lobby(self, payload: GroupLobbyOpenRequest) -> dict:
        self._ensure_group_chat(payload.chat_type)
        if not payload.actor_is_admin:
            raise AuthorizationError("Only chat admins can open a group lobby")

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

        async for db in self._iter_db():
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
        async for db in self._iter_db():
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

        async for db in self._iter_db():
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
