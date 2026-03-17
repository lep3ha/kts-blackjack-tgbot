from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now_naive
from app.domain.blackjack.context import BlackjackSessionContext, PlayerSlotSnapshot
from app.errors import NotFoundError, StateConflictError
from app.models import ChatMode, GameSession, ParticipantStatus, Player, PlayerToSession, SessionStatus, State


class BlackjackRepository:
    # Привязывает repository к конкретной async DB session.
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_id: Optional[int] = None

    # Загружает сессию и игроков; автоматические фазы не восстанавливаются из журнала.
    async def load_context(
        self,
        session_id: int,
        *,
        for_update: bool = True,
        turn_timeout_seconds: int = 30,
    ) -> BlackjackSessionContext:
        self.session_id = session_id

        session_query = select(GameSession).where(GameSession.id == session_id)
        if for_update:
            session_query = session_query.with_for_update()
        session_result = await self.db.execute(session_query)
        session = session_result.scalar_one_or_none()
        if session is None:
            raise NotFoundError("Session not found")

        seats_query = (
            select(PlayerToSession, Player.bank)
            .join(Player, Player.id == PlayerToSession.player_id)
            .where(PlayerToSession.session_id == session_id)
            .order_by(PlayerToSession.position)
        )
        if for_update:
            seats_query = seats_query.with_for_update()
        seats_result = await self.db.execute(seats_query)
        seats = [
            PlayerSlotSnapshot(
                player_to_session_id=seat.id,
                player_id=seat.player_id,
                position=seat.position,
                participant_status=seat.participant_status,
                bet=seat.bet,
                cards=list(seat.cards or []),
                bank=bank,
            )
            for seat, bank in seats_result.all()
        ]

        return BlackjackSessionContext(
            session_id=session.id,
            deck_id=session.deck_id,
            status=session.status,
            chat_mode=session.chat_mode,
            turn_version=session.turn_version,
            state=self._derive_state(session),
            dealer_cards=list(session.dealer_cards or []),
            current_position=session.current_position,
            current_timer=session.current_timer,
            count_players=session.count_players,
            players=seats,
            turn_timeout_seconds=turn_timeout_seconds,
        )

    # Сохраняет стартовую раздачу и переводит сессию в активную фазу.
    async def persist_initial_deal(
        self,
        context: BlackjackSessionContext,
        *,
        player_cards: dict[int, list[str]],
        dealer_cards: list[str],
    ) -> None:
        for player in context.players:
            cards = list(player_cards[player.position])
            player.cards = cards
            player.participant_status = ParticipantStatus.active
            await self.db.execute(
                update(PlayerToSession)
                .where(PlayerToSession.id == player.player_to_session_id)
                .values(cards=cards, participant_status=ParticipantStatus.active)
            )
            await self._append_state(
                position=player.position,
                action="deal",
                details={"cards": cards, "actor": "player"},
            )

        context.dealer_cards = list(dealer_cards)
        context.status = SessionStatus.in_progress
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(
                status=SessionStatus.in_progress,
                dealer_cards=context.dealer_cards,
                current_position=None,
                current_timer=None,
            )
        )
        await self._append_state(
            position=context.first_position(),
            action="deal_dealer",
            details={"cards": context.dealer_cards, "actor": "dealer"},
        )

    # Сохраняет передачу хода следующему игроку или завершение очереди игроков.
    async def persist_turn_assignment(
        self,
        context: BlackjackSessionContext,
        *,
        position: Optional[int],
        timer: Optional[datetime],
        action: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        context.status = SessionStatus.in_progress
        context.turn_version += 1
        context.current_position = position
        context.current_timer = timer
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(
                current_position=position,
                current_timer=timer,
                status=SessionStatus.in_progress,
                turn_version=context.turn_version,
            )
        )
        await self._append_state(position=position, action=action, details=details or {})

    # Сохраняет результат конкретного действия игрока и обновляет очередь ходов.
    async def persist_player_move(
        self,
        context: BlackjackSessionContext,
        *,
        position: int,
        action: str,
        cards: list[str],
        bet: int,
        next_position: Optional[int],
        next_timer: Optional[datetime],
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        player = context.player_by_position(position)
        if player is None:
            raise StateConflictError("Player not found in session context")

        player.cards = list(cards)
        player.bet = bet
        context.status = SessionStatus.in_progress
        context.turn_version += 1

        await self.db.execute(
            update(PlayerToSession)
            .where(PlayerToSession.id == player.player_to_session_id)
            .values(cards=player.cards, bet=player.bet)
        )

        context.current_position = next_position
        context.current_timer = next_timer
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(
                current_position=next_position,
                current_timer=next_timer,
                status=SessionStatus.in_progress,
                turn_version=context.turn_version,
            )
        )

        await self._append_state(position=position, action=action, details=details or {})
        if next_position is None:
            await self._append_state(position=position, action="players_done", details={"actor": "system"})

    # Сохраняет системный timeout как завершение хода игрока.
    async def persist_timeout(
        self,
        context: BlackjackSessionContext,
        *,
        position: int,
        next_position: Optional[int],
        next_timer: Optional[datetime],
    ) -> None:
        context.status = SessionStatus.in_progress
        context.turn_version += 1
        context.current_position = next_position
        context.current_timer = next_timer
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(
                current_position=next_position,
                current_timer=next_timer,
                status=SessionStatus.in_progress,
                turn_version=context.turn_version,
            )
        )
        await self._append_state(position=position, action="timeout", details={"actor": "system"})
        if next_position is None:
            await self._append_state(position=position, action="players_done", details={"actor": "system"})

    # Фиксирует карты дилера и его добор в журнале состояний.
    async def persist_dealer_turn(
        self,
        context: BlackjackSessionContext,
        *,
        dealer_cards: list[str],
        drawn_cards: list[str],
    ) -> None:
        context.dealer_cards = list(dealer_cards)
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(dealer_cards=context.dealer_cards, current_position=None, current_timer=None)
        )
        for card in drawn_cards:
            await self._append_state(
                position=context.first_position(),
                action="dealer_hit",
                details={"card": card, "actor": "dealer"},
            )
        await self._append_state(
            position=context.first_position(),
            action="dealer_stand",
            details={"cards": context.dealer_cards, "actor": "dealer"},
        )

    # Применяет расчёт выплат и закрывает игровую сессию.
    async def persist_resolution(
        self,
        context: BlackjackSessionContext,
        *,
        settlements: list[dict[str, Any]],
    ) -> None:
        for settlement in settlements:
            player = context.player_by_position(settlement["position"])
            if player is None:
                continue
            player.bank += settlement["delta"]
            player.participant_status = ParticipantStatus.settled
            await self.db.execute(
                update(Player)
                .where(Player.id == player.player_id)
                .values(bank=player.bank)
            )
            await self.db.execute(
                update(PlayerToSession)
                .where(PlayerToSession.id == player.player_to_session_id)
                .values(participant_status=ParticipantStatus.settled)
            )
            await self._append_state(
                position=player.position,
                action="result",
                details={
                    "result": settlement["result"],
                    "delta": settlement["delta"],
                    "actor": "system",
                },
            )

        context.status = SessionStatus.closed
        context.current_position = None
        context.current_timer = None
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(status=SessionStatus.closed, current_position=None, current_timer=None, turn_version=context.turn_version)
        )
        await self._append_state(
            position=context.first_position(),
            action="session_closed",
            details={"actor": "system"},
        )

    async def persist_partial_settlement(
        self,
        context: BlackjackSessionContext,
        *,
        position: int,
        participant_status: ParticipantStatus,
        settlement: dict[str, Any],
        next_position: Optional[int],
        next_timer: Optional[datetime],
        close_session: bool = False,
    ) -> None:
        player = context.player_by_position(position)
        if player is None:
            raise StateConflictError("Player not found in session context")

        context.turn_version += 1

        player.bank += settlement["delta"]
        player.participant_status = participant_status

        await self.db.execute(
            update(Player)
            .where(Player.id == player.player_id)
            .values(bank=player.bank)
        )
        await self.db.execute(
            update(PlayerToSession)
            .where(PlayerToSession.id == player.player_to_session_id)
            .values(participant_status=participant_status)
        )
        await self._append_state(
            position=player.position,
            action="result",
            details={
                "result": settlement["result"],
                "delta": settlement["delta"],
                "actor": "system",
                "reason": "player_stop",
            },
        )
        await self._append_state(
            position=player.position,
            action="player_stopped",
            details={"actor": "system"},
        )

        context.current_position = next_position
        context.current_timer = next_timer

        if close_session:
            context.status = SessionStatus.closed
            await self.db.execute(
                update(GameSession)
                .where(GameSession.id == context.session_id)
                .values(status=SessionStatus.closed, current_position=None, current_timer=None, turn_version=context.turn_version)
            )
            await self._append_state(
                position=context.first_position(),
                action="session_closed",
                details={"actor": "system", "reason": "player_stop"},
            )
            return

        context.status = SessionStatus.in_progress
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(
                current_position=next_position,
                current_timer=next_timer,
                status=SessionStatus.in_progress,
                turn_version=context.turn_version,
            )
        )

    # Фиксирует все изменения текущей транзакции в БД.
    async def commit(self) -> None:
        await self.db.commit()

    # Откатывает текущую транзакцию при ошибке в доменном сценарии.
    async def rollback(self) -> None:
        await self.db.rollback()

    # Добавляет запись в журнал действий игры.
    async def _append_state(
        self,
        *,
        position: Optional[int],
        action: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        normalized_position = position if position is not None and position > 0 else 1
        state_entry = State(
            session_id=self.session_id or 0,
            position=normalized_position,
            action=action,
            time=utc_now_naive(),
            details=details or {},
        )
        self.db.add(state_entry)
        await self.db.flush([state_entry])

    # Восстанавливает только сохраняемые состояния машины из статуса сессии.
    def _derive_state(self, session: GameSession) -> str:
        if session.status == SessionStatus.closed:
            return "closed"
        if session.status == SessionStatus.stopped:
            return "closed"
        if session.status == SessionStatus.lobby_open:
            return "waiting"
        if session.status == SessionStatus.in_progress:
            return "player_turn"
        return "player_turn"