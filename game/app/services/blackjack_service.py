from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional, Tuple

from statemachine import State, StateChart
from statemachine.exceptions import TransitionNotAllowed

from app.errors import ApiError, StateConflictError, StateTransitionError
from app.domain.blackjack import (
    ActionRuntimeContext,
    BlackjackStateMachineSettings,
    DealerPolicy,
    EventContextBuilder,
    PlayerTurnRules,
    PlayerActionDispatcher,
    SettlementPolicy,
)
from app.core.datetime_utils import utc_now_naive
from app.domain.blackjack.context import BlackjackSessionContext
from app.services.blackjack_repository import BlackjackRepository


RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠️", "♥️", "♦️", "♣️"]
SETTINGS = BlackjackStateMachineSettings()


# Возвращает случайную карту в формате ранг+масть.
def draw_card() -> str:
    return f"{random.choice(RANKS)}{random.choice(SUITS)}"


def _extract_rank(card: str) -> str:
    # Rank is always a prefix (e.g. "10", "A", "K"). This avoids
    # assumptions about suit length (e.g. "♥️" is two code points).
    for rank in sorted(RANKS, key=len, reverse=True):
        if card.startswith(rank):
            return rank
    raise ValueError(f"Invalid card format: {card}")


# Считает очки руки и отдельно помечает натуральный blackjack.
def compute_score(cards: list[str]) -> Tuple[int, bool]:
    total = 0
    aces = 0
    for card in cards:
        rank = _extract_rank(card)
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


class BlackjackService(StateChart[BlackjackSessionContext]):
    allow_event_without_transition = False
    catch_errors_as_events = False

    waiting = State(initial=True)
    dealing = State()
    player_turn = State()
    dealer_turn = State()
    resolving = State()
    closed = State(final=True)

    start_round = waiting.to(dealing, validators="validate_can_start", on="deal_opening_hands")
    finish_deal = (
        dealing.to(player_turn, cond="has_players_to_act", on="activate_next_player")
        | dealing.to(dealer_turn, unless="has_players_to_act", on="mark_players_complete")
    )
    player_move = (
        player_turn.to(player_turn, validators="validate_player_move", cond="keeps_same_turn", on="apply_player_move")
        | player_turn.to(player_turn, validators="validate_player_move", cond="advances_to_next_player", on="apply_player_move")
        | player_turn.to(dealer_turn, validators="validate_player_move", cond="advances_to_dealer", on="apply_player_move")
    )
    timeout_turn = (
        player_turn.to(player_turn, validators="validate_timeout_request", cond="advances_to_next_player", on="apply_timeout")
        | player_turn.to(dealer_turn, validators="validate_timeout_request", cond="advances_to_dealer", on="apply_timeout")
    )
    play_dealer = dealer_turn.to(resolving, on="run_dealer_turn")
    finalize_round = resolving.to(closed, on="settle_round")

    # Инициализирует state machine поверх уже загруженного контекста сессии.
    def __init__(self, repository: BlackjackRepository, model: BlackjackSessionContext):
        self.repository = repository
        self.settings = SETTINGS
        self.turn_rules = PlayerTurnRules(
            score_fn=compute_score,
            player_actions=self.settings.player_actions,
        )
        self.dealer_policy = DealerPolicy(
            score_fn=compute_score,
            draw_card_fn=draw_card,
            stand_score=self.settings.dealer_stand_score,
        )
        self.settlement_policy = SettlementPolicy(score_fn=compute_score)
        self.event_context_builder = EventContextBuilder(
            draw_card_fn=draw_card,
            score_fn=compute_score,
            next_playable_position_fn=self.turn_rules.next_playable_position,
        )
        self.player_action_dispatcher = PlayerActionDispatcher()
        super().__init__(model=model, start_value=model.state)

    @classmethod
    # Загружает контекст игры из БД и создаёт готовый экземпляр машины.
    async def load(
        cls,
        db,
        session_id: int,
        *,
        turn_timeout_seconds: int = 30,
        for_update: bool = True,
    ) -> "BlackjackService":
        repository = BlackjackRepository(db)
        context = await repository.load_context(
            session_id,
            for_update=for_update,
            turn_timeout_seconds=turn_timeout_seconds,
        )
        return cls(repository=repository, model=context)

    # Запускает новую раздачу и доводит машину до первого активного хода.
    async def start_session(self) -> BlackjackSessionContext:
        return await self._run_transaction(self._start_session_flow)

    # Применяет пользовательское действие и при необходимости запускает дилера и расчёт.
    async def apply_action(self, position: int, action: str) -> BlackjackSessionContext:
        async def runner() -> BlackjackSessionContext:
            self._ensure_event_available("player_move")
            await self.player_move(position=position, action=action)
            await self._drain_terminal_phases()
            return self.model

        return await self._run_transaction(runner)

    # Обрабатывает истечение таймера для текущего или явно переданного игрока.
    async def handle_timeout(self, position: Optional[int] = None) -> BlackjackSessionContext:
        async def runner() -> BlackjackSessionContext:
            self._ensure_event_available("timeout_turn")
            timeout_position = position if position is not None else self.model.current_position
            await self.timeout_turn(position=timeout_position)
            await self._drain_terminal_phases()
            return self.model

        return await self._run_transaction(runner)

    # Возвращает список событий, доступных из текущего состояния машины.
    def available_events(self) -> list[str]:
        return [event.id for event in self.allowed_events]

    # Возвращает список доступных действий игрока для текущего состояния и позиции.
    def available_moves(self) -> list[str]:
        if "player_move" not in self.available_events():
            return []

        position = self.model.current_position
        if position is None:
            return []
        seat = self.model.player_by_position(position)
        if seat is None:
            return []

        moves: list[str] = []
        for action in ("hit", "stand", "double"):
            try:
                self.turn_rules.validate_player_move(self.model, position=position, action=action, seat=seat)
            except ApiError:
                continue
            moves.append(action)
        return moves

    # Подготавливает общий runtime-контекст для guards и action callbacks.
    def prepare_event(self, event=None, position: Optional[int] = None, action: Optional[str] = None):
        return self.event_context_builder.build(
            model=self.model,
            event_id=getattr(event, "id", None),
            event_token=id(event) if event is not None else None,
            position=position,
            action=action,
        )

    # Проверяет, что сессию действительно можно перевести из ожидания в раздачу.
    def validate_can_start(self) -> None:
        self.turn_rules.validate_can_start(self.model)

    # Валидирует допустимость действия игрока до выбора перехода state machine.
    def validate_player_move(self, position: int, action: str, seat) -> None:
        self.turn_rules.validate_player_move(self.model, position=position, action=action, seat=seat)

    # Валидирует, что таймер реально истёк и событие можно трактовать как timeout.
    def validate_timeout_request(self, position: int, seat) -> None:
        self.turn_rules.validate_timeout_request(
            self.model,
            position=position,
            seat=seat,
            timer_expired=self._timer_expired(),
        )

    # Определяет, остались ли за столом игроки, которые ещё могут ходить.
    def has_players_to_act(self) -> bool:
        return self._first_playable_position() is not None

    # Разрешает оставить ход у текущего игрока после безопасного hit.
    def keeps_same_turn(self, action: str, projected_score: int) -> bool:
        return self.turn_rules.keeps_same_turn(action, projected_score)

    # Разрешает переход к следующему игроку, если текущий ход завершён.
    def advances_to_next_player(self, action: str, projected_score: int, next_position: Optional[int]) -> bool:
        return self.turn_rules.advances_to_next_player(action, projected_score, next_position)

    # Разрешает переход к ходу дилера, когда активных игроков больше не осталось.
    def advances_to_dealer(self, action: str, projected_score: int, next_position: Optional[int]) -> bool:
        return self.turn_rules.advances_to_dealer(action, projected_score, next_position)

    # Выполняет стартовую раздачу игрокам и дилеру.
    async def deal_opening_hands(self) -> None:
        player_cards = {player.position: [draw_card(), draw_card()] for player in self.model.players}
        dealer_cards = [draw_card(), draw_card()]
        await self.repository.persist_initial_deal(
            self.model,
            player_cards=player_cards,
            dealer_cards=dealer_cards,
        )

    # Назначает первого игрока на ход и запускает для него таймер.
    async def activate_next_player(self) -> None:
        next_position = self._first_playable_position()
        if next_position is None:
            raise StateConflictError("No player available for turn assignment")
        await self.repository.persist_turn_assignment(
            self.model,
            position=next_position,
            timer=self._next_turn_timer(),
            action="turn_started",
            details={"actor": "system"},
        )

    # Фиксирует, что этап действий игроков завершён и очередь переходит дилеру.
    async def mark_players_complete(self) -> None:
        await self.repository.persist_turn_assignment(
            self.model,
            position=None,
            timer=None,
            action="players_done",
            details={"actor": "system"},
        )

    # Применяет выбранное игроком действие и синхронизирует результат с БД.
    async def apply_player_move(
        self,
        *,
        position: int,
        action: str,
        seat,
        drawn_card: Optional[str],
        projected_cards: list[str],
        projected_score: int,
        next_position: Optional[int],
        target,
    ) -> None:
        decision = self.player_action_dispatcher.dispatch(
            ActionRuntimeContext(
                position=position,
                action=action,
                seat=seat,
                target_state_id=target.id,
                drawn_card=drawn_card,
                projected_cards=projected_cards,
                projected_score=projected_score,
                next_position=next_position,
            )
        )
        next_timer = self._next_turn_timer() if decision.should_schedule_timer else None

        await self.repository.persist_player_move(
            self.model,
            position=position,
            action=action,
            cards=decision.cards,
            bet=decision.bet,
            next_position=decision.next_position,
            next_timer=next_timer,
            details=decision.details,
        )

    # Превращает истечение таймера в системный переход и обновляет очередь хода.
    async def apply_timeout(self, *, position: int, next_position: Optional[int], target) -> None:
        next_timer = self._next_turn_timer() if target.id == "player_turn" else None
        await self.repository.persist_timeout(
            self.model,
            position=position,
            next_position=next_position,
            next_timer=next_timer,
        )

    # Исполняет детерминированную фазу дилера до условия остановки.
    async def run_dealer_turn(self) -> None:
        dealer_cards, drawn_cards = self.dealer_policy.play_turn(list(self.model.dealer_cards))

        await self.repository.persist_dealer_turn(
            self.model,
            dealer_cards=dealer_cards,
            drawn_cards=drawn_cards,
        )

    # Считает результаты раунда для всех игроков и подготавливает выплаты.
    async def settle_round(self) -> None:
        settlements = self.settlement_policy.build_settlements(self.model.players, self.model.dealer_cards)

        await self.repository.persist_resolution(self.model, settlements=settlements)

    # Запускает стартовую цепочку переходов для новой игровой сессии.
    async def _start_session_flow(self) -> BlackjackSessionContext:
        await self.start_round()
        await self.finish_deal()
        await self._drain_terminal_phases()
        return self.model

    # Оборачивает сценарий игры в commit/rollback транзакцию.
    async def _run_transaction(self, callback):
        try:
            result = await callback()
            await self.repository.commit()
            return result
        except TransitionNotAllowed as exc:
            await self.repository.rollback()
            raise StateTransitionError(self._build_transition_error(exc.event)) from exc
        except Exception:
            await self.repository.rollback()
            raise

    # Проверяет доступность события в текущем состоянии до запуска перехода.
    def _ensure_event_available(self, event_id: str) -> None:
        if event_id not in self.available_events():
            raise StateTransitionError(self._build_transition_error(event_id))

    # Формирует диагностическое сообщение для невалидных переходов.
    def _build_transition_error(self, event_id: str) -> str:
        allowed = self.available_events()
        allowed_repr = ", ".join(allowed) if allowed else "none"
        return f"Event '{event_id}' is not allowed from state '{self.current_state.id}'. Allowed events: {allowed_repr}"

    # Автоматически доигрывает фазы дилера и расчёта, если машина уже дошла до них.
    async def _drain_terminal_phases(self) -> None:
        while True:
            if self.dealer_turn.is_active:
                await self.play_dealer()
                continue
            if self.resolving.is_active:
                await self.finalize_round()
                continue
            break

    # Находит первого игрока, у которого рука ещё может сделать ход.
    def _first_playable_position(self) -> Optional[int]:
        return self.turn_rules.first_playable_position(self.model.players)

    # Вычисляет дедлайн следующего хода на основе настроек контекста.
    def _next_turn_timer(self) -> datetime:
        return utc_now_naive() + timedelta(seconds=self.model.turn_timeout_seconds)

    # Проверяет, истёк ли дедлайн текущего активного хода.
    def _timer_expired(self) -> bool:
        if self.model.current_timer is None:
            return False
        return self.model.current_timer <= utc_now_naive()