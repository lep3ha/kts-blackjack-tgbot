from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now_naive
from app.domain.blackjack.context import BlackjackSessionContext, PlayerSlotSnapshot
from app.errors import NotFoundError, StateConflictError
from app.models import ChatMode, GameSession, ParticipantStatus, Player, PlayerHand, PlayerToSession, SessionStatus, State


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
        seat_rows = seats_result.all()
        seat_ids = [seat.id for seat, _ in seat_rows]

        hands_by_seat: dict[int, dict[int, PlayerHand]] = defaultdict(dict)
        if seat_ids:
            hands_query = (
                select(PlayerHand)
                .where(
                    PlayerHand.player_to_session_id.in_(seat_ids),
                )
                .order_by(PlayerHand.player_to_session_id, PlayerHand.hand_index)
            )
            if for_update:
                hands_query = hands_query.with_for_update()
            hands_result = await self.db.execute(hands_query)
            for hand in hands_result.scalars().all():
                hands_by_seat[hand.player_to_session_id][hand.hand_index] = hand

        seats = []
        for seat, bank in seat_rows:
            seat_hands = hands_by_seat.get(seat.id, {})
            active_hand_index = 0
            if seat.position == session.current_position and session.current_hand_index is not None:
                active_hand_index = session.current_hand_index

            hand = seat_hands.get(active_hand_index) or seat_hands.get(0)
            cards = list(hand.cards or []) if hand is not None else list(seat.cards or [])
            bet = hand.bet if hand is not None else seat.bet
            status = hand.participant_status if hand is not None else seat.participant_status
            seats.append(
                PlayerSlotSnapshot(
                    player_to_session_id=seat.id,
                    player_id=seat.player_id,
                    position=seat.position,
                    participant_status=status,
                    bet=bet,
                    cards=cards,
                    bank=bank,
                    insurance_bet=int(seat.insurance_bet or 0),
                )
            )

        return BlackjackSessionContext(
            session_id=session.id,
            deck_id=session.deck_id,
            status=session.status,
            chat_mode=session.chat_mode,
            turn_version=session.turn_version,
            state=self._derive_state(session),
            dealer_cards=list(session.dealer_cards or []),
            current_position=session.current_position,
            current_hand_index=session.current_hand_index,
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
                .values(cards=cards, participant_status=ParticipantStatus.active, insurance_bet=0)
            )
            await self._upsert_hand(
                player_to_session_id=player.player_to_session_id,
                hand_index=0,
                cards=cards,
                bet=player.bet,
                participant_status=ParticipantStatus.active,
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
        context.current_hand_index = 0 if position is not None else None
        context.current_timer = timer
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(
                current_position=position,
                current_hand_index=context.current_hand_index,
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

        active_hand_index = context.current_hand_index if context.current_hand_index is not None else 0
        played_hand_cards = list(cards)
        played_hand_bet = bet

        player.cards = list(cards)
        player.bet = bet
        context.status = SessionStatus.in_progress
        context.turn_version += 1

        is_insurance_action = action == "insurance"
        if is_insurance_action:
            insurance_bet = int((details or {}).get("insurance_bet") or 0)
            if insurance_bet <= 0:
                raise StateConflictError("Insurance amount is invalid")
            if player.insurance_bet > 0:
                raise StateConflictError("Insurance already purchased for this player")
            required_bank = player.bet + insurance_bet
            if player.bank < required_bank:
                raise StateConflictError("Insufficient funds to buy insurance")

            player.bank -= insurance_bet
            player.insurance_bet = insurance_bet

            await self.db.execute(
                update(Player)
                .where(Player.id == player.player_id)
                .values(bank=player.bank)
            )
            await self.db.execute(
                update(PlayerToSession)
                .where(PlayerToSession.id == player.player_to_session_id)
                .values(insurance_bet=insurance_bet)
            )

            context.current_position = position
            context.current_hand_index = active_hand_index
            context.current_timer = next_timer
            await self.db.execute(
                update(GameSession)
                .where(GameSession.id == context.session_id)
                .values(
                    current_position=position,
                    current_hand_index=active_hand_index,
                    current_timer=next_timer,
                    status=SessionStatus.in_progress,
                    turn_version=context.turn_version,
                )
            )

            await self._append_state(position=position, action=action, details=details or {})
            return

        is_split_action = action == "split" and "split_second_hand_cards" in (details or {})
        if is_split_action:
            hand_count = await self._count_hands(player.player_to_session_id)
            if hand_count >= 4:
                raise StateConflictError("Split hand limit reached")

            insertion_index = active_hand_index + 1
            await self._shift_hands_right(
                player_to_session_id=player.player_to_session_id,
                from_hand_index=insertion_index,
                max_hand_index=3,
            )

            split_second_cards = list((details or {}).get("split_second_hand_cards", []))
            split_second_draw_card = (details or {}).get("split_second_hand_draw_card")
            await self._upsert_hand(
                player_to_session_id=player.player_to_session_id,
                hand_index=active_hand_index,
                cards=player.cards,
                bet=player.bet,
                participant_status=ParticipantStatus.active,
            )
            await self._upsert_hand(
                player_to_session_id=player.player_to_session_id,
                hand_index=active_hand_index + 1,
                cards=split_second_cards,
                bet=player.bet,
                participant_status=ParticipantStatus.active,
            )
            await self.db.execute(
                update(PlayerToSession)
                .where(PlayerToSession.id == player.player_to_session_id)
                .values(cards=player.cards, bet=player.bet, participant_status=ParticipantStatus.active)
            )

            resolved_next_position: Optional[int] = position
            resolved_hand_index: Optional[int] = active_hand_index
            resolved_timer = next_timer

            # If the current split hand is immediately terminal (e.g. blackjack),
            # auto-advance to the next playable hand/player without waiting for timeout.
            if not self._hand_can_act(player.cards):
                await self._sync_primary_hand_status(
                    player_to_session_id=player.player_to_session_id,
                    participant_status=ParticipantStatus.inactive,
                    hand_index=active_hand_index,
                )

                next_hand = await self._next_active_hand_index(player.player_to_session_id, active_hand_index)
                while next_hand is not None:
                    await self._materialize_delayed_split_card(
                        context=context,
                        position=position,
                        player_to_session_id=player.player_to_session_id,
                        hand_index=next_hand,
                    )
                    next_hand_row = await self._load_hand(player.player_to_session_id, next_hand)
                    if next_hand_row is None:
                        resolved_next_position = position
                        resolved_hand_index = next_hand
                        break

                    if (
                        next_hand == active_hand_index + 1
                        and isinstance(split_second_draw_card, str)
                        and split_second_draw_card
                        and len(list(next_hand_row.cards or [])) == 1
                    ):
                        next_hand_cards = list(next_hand_row.cards or [])
                        next_hand_cards.append(split_second_draw_card)
                        next_hand_row.cards = next_hand_cards
                        await self.db.flush([next_hand_row])

                    if self._hand_can_act(list(next_hand_row.cards or [])):
                        resolved_next_position = position
                        resolved_hand_index = next_hand
                        resolved_timer = next_timer
                        player.cards = list(next_hand_row.cards or [])
                        player.bet = int(next_hand_row.bet)
                        break

                    await self._sync_primary_hand_status(
                        player_to_session_id=player.player_to_session_id,
                        participant_status=ParticipantStatus.inactive,
                        hand_index=next_hand,
                    )
                    next_hand = await self._next_active_hand_index(player.player_to_session_id, next_hand)
                else:
                    resolved_next_position = self._next_playable_position_after(context, position)
                    resolved_hand_index = 0 if resolved_next_position is not None else None
                    resolved_timer = next_timer if resolved_next_position is not None else None

                    if resolved_next_position is None:
                        player.participant_status = ParticipantStatus.inactive

            context.current_position = resolved_next_position
            context.current_hand_index = resolved_hand_index
            context.current_timer = resolved_timer
            await self.db.execute(
                update(GameSession)
                .where(GameSession.id == context.session_id)
                .values(
                    current_position=resolved_next_position,
                    current_hand_index=resolved_hand_index,
                    current_timer=resolved_timer,
                    status=SessionStatus.in_progress,
                    turn_version=context.turn_version,
                )
            )

            await self._append_state(position=position, action=action, details=details or {})
            if resolved_next_position is None:
                await self._append_state(position=position, action="players_done", details={"actor": "system"})
            return

        resolved_next_position = next_position
        if resolved_next_position is None:
            resolved_hand_index = None
        elif (
            resolved_next_position == position
            and context.current_position == position
            and context.current_hand_index is not None
        ):
            # Keep active split-hand pointer when turn stays on the same player/hand.
            resolved_hand_index = context.current_hand_index
        else:
            resolved_hand_index = 0
        persisted_hand_status = player.participant_status

        # When the active hand is completed and another hand of the same player exists,
        # keep the turn on that player and switch to the next hand.
        if context.current_position == position and context.current_hand_index is not None and next_position != position:
            next_hand = await self._next_active_hand_index(player.player_to_session_id, context.current_hand_index)
            if next_hand is not None:
                persisted_hand_status = ParticipantStatus.inactive
                if next_timer is None:
                    next_timer = utc_now_naive() + timedelta(seconds=context.turn_timeout_seconds)
                await self._sync_primary_hand_status(
                    player_to_session_id=player.player_to_session_id,
                    participant_status=ParticipantStatus.inactive,
                    hand_index=context.current_hand_index,
                )

                while next_hand is not None:
                    await self._materialize_delayed_split_card(
                        context=context,
                        position=position,
                        player_to_session_id=player.player_to_session_id,
                        hand_index=next_hand,
                    )
                    next_hand_row = await self._load_hand(player.player_to_session_id, next_hand)
                    if next_hand_row is None:
                        resolved_next_position = position
                        resolved_hand_index = next_hand
                        break

                    player.cards = list(next_hand_row.cards or [])
                    player.bet = int(next_hand_row.bet)

                    if self._hand_can_act(player.cards):
                        resolved_next_position = position
                        resolved_hand_index = next_hand
                        break

                    await self._sync_primary_hand_status(
                        player_to_session_id=player.player_to_session_id,
                        participant_status=ParticipantStatus.inactive,
                        hand_index=next_hand,
                    )
                    next_hand = await self._next_active_hand_index(player.player_to_session_id, next_hand)

                if next_hand is None:
                    resolved_next_position = self._next_playable_position_after(context, position)
                    resolved_hand_index = 0 if resolved_next_position is not None else None
                    if resolved_next_position is None:
                        next_timer = None
                        player.participant_status = ParticipantStatus.inactive

        if active_hand_index == 0:
            await self.db.execute(
                update(PlayerToSession)
                .where(PlayerToSession.id == player.player_to_session_id)
                .values(cards=player.cards, bet=player.bet)
            )
        await self._upsert_hand(
            player_to_session_id=player.player_to_session_id,
            hand_index=active_hand_index,
            cards=played_hand_cards,
            bet=played_hand_bet,
            participant_status=persisted_hand_status,
        )

        context.current_position = resolved_next_position
        context.current_hand_index = resolved_hand_index
        context.current_timer = next_timer
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(
                current_position=resolved_next_position,
                current_hand_index=context.current_hand_index,
                current_timer=next_timer,
                status=SessionStatus.in_progress,
                turn_version=context.turn_version,
            )
        )

        await self._append_state(position=position, action=action, details=details or {})
        if resolved_next_position is None:
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
        context.current_hand_index = 0 if next_position is not None else None
        context.current_timer = next_timer
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(
                current_position=next_position,
                current_hand_index=context.current_hand_index,
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
            .values(dealer_cards=context.dealer_cards, current_position=None, current_hand_index=None, current_timer=None)
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
            await self._sync_all_hands_status(
                player_to_session_id=player.player_to_session_id,
                participant_status=ParticipantStatus.settled,
            )

            hand_settlements = list(settlement.get("hand_settlements") or [])
            for hand_entry in hand_settlements:
                await self._append_state(
                    position=player.position,
                    action="result_hand",
                    details={
                        "hand_index": hand_entry.get("hand_index", 0),
                        "result": hand_entry.get("result"),
                        "delta": hand_entry.get("delta"),
                        "actor": "system",
                    },
                )

            await self._append_state(
                position=player.position,
                action="result",
                details={
                    "result": settlement["result"],
                    "delta": settlement["delta"],
                    "insurance_delta": settlement.get("insurance_delta", 0),
                    "actor": "system",
                    "hand_settlements": hand_settlements,
                },
            )

        context.status = SessionStatus.closed
        context.current_position = None
        context.current_hand_index = None
        context.current_timer = None
        await self.db.execute(
            update(GameSession)
            .where(GameSession.id == context.session_id)
            .values(
                status=SessionStatus.closed,
                current_position=None,
                current_hand_index=None,
                current_timer=None,
                turn_version=context.turn_version,
            )
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
        await self._sync_primary_hand_status(
            player_to_session_id=player.player_to_session_id,
            participant_status=participant_status,
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
        context.current_hand_index = 0 if next_position is not None else None
        context.current_timer = next_timer

        if close_session:
            context.status = SessionStatus.closed
            await self.db.execute(
                update(GameSession)
                .where(GameSession.id == context.session_id)
                .values(
                    status=SessionStatus.closed,
                    current_position=None,
                    current_hand_index=None,
                    current_timer=None,
                    turn_version=context.turn_version,
                )
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
                current_hand_index=context.current_hand_index,
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

    async def _upsert_hand(
        self,
        *,
        player_to_session_id: int,
        hand_index: int,
        cards: list[str],
        bet: int,
        participant_status: ParticipantStatus,
    ) -> None:
        existing = await self.db.execute(
            select(PlayerHand).where(
                PlayerHand.player_to_session_id == player_to_session_id,
                PlayerHand.hand_index == hand_index,
            )
        )
        hand = existing.scalar_one_or_none()
        if hand is None:
            hand = PlayerHand(
                player_to_session_id=player_to_session_id,
                hand_index=hand_index,
                cards=list(cards),
                bet=bet,
                participant_status=participant_status,
                created_at=utc_now_naive(),
            )
            self.db.add(hand)
            await self.db.flush([hand])
            return

        hand.cards = list(cards)
        hand.bet = bet
        hand.participant_status = participant_status
        await self.db.flush([hand])

    async def _sync_primary_hand_status(
        self,
        *,
        player_to_session_id: int,
        participant_status: ParticipantStatus,
        hand_index: int = 0,
    ) -> None:
        await self.db.execute(
            update(PlayerHand)
            .where(
                PlayerHand.player_to_session_id == player_to_session_id,
                PlayerHand.hand_index == hand_index,
            )
            .values(participant_status=participant_status)
        )

    async def _sync_all_hands_status(
        self,
        *,
        player_to_session_id: int,
        participant_status: ParticipantStatus,
    ) -> None:
        await self.db.execute(
            update(PlayerHand)
            .where(PlayerHand.player_to_session_id == player_to_session_id)
            .values(participant_status=participant_status)
        )

    async def _next_active_hand_index(self, player_to_session_id: int, current_hand_index: int) -> int | None:
        result = await self.db.execute(
            select(PlayerHand.hand_index)
            .where(
                PlayerHand.player_to_session_id == player_to_session_id,
                PlayerHand.hand_index > current_hand_index,
                PlayerHand.participant_status == ParticipantStatus.active,
            )
            .order_by(PlayerHand.hand_index)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _count_hands(self, player_to_session_id: int) -> int:
        result = await self.db.execute(
            select(PlayerHand.id).where(PlayerHand.player_to_session_id == player_to_session_id)
        )
        return len(result.scalars().all())

    async def _shift_hands_right(self, *, player_to_session_id: int, from_hand_index: int, max_hand_index: int) -> None:
        if from_hand_index > max_hand_index:
            return
        for index in range(max_hand_index, from_hand_index - 1, -1):
            await self.db.execute(
                update(PlayerHand)
                .where(
                    PlayerHand.player_to_session_id == player_to_session_id,
                    PlayerHand.hand_index == index,
                )
                .values(hand_index=index + 1)
            )

    async def _load_hand(self, player_to_session_id: int, hand_index: int) -> Optional[PlayerHand]:
        result = await self.db.execute(
            select(PlayerHand).where(
                PlayerHand.player_to_session_id == player_to_session_id,
                PlayerHand.hand_index == hand_index,
            )
        )
        return result.scalar_one_or_none()

    async def _materialize_delayed_split_card(
        self,
        *,
        context: BlackjackSessionContext,
        position: int,
        player_to_session_id: int,
        hand_index: int,
    ) -> None:
        hand = await self._load_hand(player_to_session_id, hand_index)
        if hand is None:
            return

        cards = list(hand.cards or [])
        if len(cards) != 1:
            return
        seed_card = cards[0]

        parent_hand_index = hand_index - 1
        split_state_result = await self.db.execute(
            select(State.details)
            .where(
                State.session_id == context.session_id,
                State.position == position,
                State.action == "split",
            )
            .order_by(State.id.desc())
        )

        delayed_card: Optional[str] = None
        fallback_delayed_card: Optional[str] = None
        for raw_details in split_state_result.scalars().all():
            details = raw_details or {}
            raw_delayed = details.get("split_second_hand_draw_card")
            if not (isinstance(raw_delayed, str) and raw_delayed):
                continue

            second_cards = details.get("split_second_hand_cards")
            seed_matches = (
                isinstance(second_cards, list)
                and len(second_cards) == 1
                and isinstance(second_cards[0], str)
                and second_cards[0] == seed_card
            )

            if seed_matches and fallback_delayed_card is None:
                fallback_delayed_card = raw_delayed

            if int(details.get("hand_index", -1)) != parent_hand_index:
                continue

            if seed_matches:
                delayed_card = raw_delayed
                break

        if delayed_card is None:
            delayed_card = fallback_delayed_card

        if delayed_card is None:
            return

        cards.append(delayed_card)
        hand.cards = cards
        await self.db.flush([hand])

    def _next_playable_position_after(self, context: BlackjackSessionContext, current_position: int) -> Optional[int]:
        for player in sorted(context.players, key=lambda item: item.position):
            if player.position <= current_position:
                continue
            if self._hand_can_act(player.cards):
                return player.position
        return None

    def _hand_can_act(self, cards: list[str]) -> bool:
        score, blackjack = self._score(cards)
        return not blackjack and score < 21

    def _score(self, cards: list[str]) -> tuple[int, bool]:
        total = 0
        aces = 0
        for card in cards:
            rank = self._card_rank(card)
            if rank == "A":
                aces += 1
                total += 1
            elif rank in {"J", "Q", "K", "10"}:
                total += 10
            else:
                total += int(rank)

        for _ in range(aces):
            if total + 10 <= 21:
                total += 10
        return total, len(cards) == 2 and total == 21

    def _card_rank(self, card: str) -> str:
        normalized = card.upper()
        if normalized.startswith("10"):
            return "10"

        rank = normalized[:1]
        if rank in {"A", "K", "Q", "J", "T", "2", "3", "4", "5", "6", "7", "8", "9"}:
            return rank
        raise StateConflictError("Invalid card format")

    async def load_unsettled_hands_by_position(self, session_id: int) -> dict[int, list[dict[str, Any]]]:
        query = (
            select(PlayerToSession.position, PlayerHand.hand_index, PlayerHand.cards, PlayerHand.bet, PlayerHand.participant_status)
            .join(PlayerToSession, PlayerToSession.id == PlayerHand.player_to_session_id)
            .where(
                PlayerToSession.session_id == session_id,
                PlayerHand.participant_status != ParticipantStatus.settled,
            )
            .order_by(PlayerToSession.position, PlayerHand.hand_index)
        )
        result = await self.db.execute(query)

        payload: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for position, hand_index, cards, bet, participant_status in result.all():
            if participant_status not in {ParticipantStatus.active, ParticipantStatus.inactive}:
                continue
            payload[position].append(
                {
                    "hand_index": hand_index,
                    "cards": list(cards or []),
                    "bet": bet,
                }
            )
        return payload

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