# Blackjack Architecture

## Общая идея

Архитектура `game` разделена на пять уровней:
1. HTTP API
2. accessors
3. state machine orchestration
4. domain rules/policies
5. persistence repository

Такое разделение позволяет менять правила игры отдельно от transport-контрактов и БД-слоя.

## Главные модули

### `app/services/blackjack_service.py`

Тонкий orchestration слой state machine:
- объявляет состояния и переходы;
- запускает публичные операции `start_session`, `apply_action`, `handle_timeout`;
- управляет commit/rollback;
- выполняет auto-drain terminal phases.

### `app/domain/blackjack/turn_rules.py`

Содержит validators и branching logic для действий игроков и timeout.

### `app/domain/blackjack/event_context_builder.py`

Строит projected runtime context для текущего события.

### `app/domain/blackjack/action_dispatch.py`

Унифицирует dispatch `hit/stand/double` в payload для repository.

### `app/domain/blackjack/dealer_policy.py`

Определяет поведение дилера.

### `app/domain/blackjack/settlement_policy.py`

Считает результаты hands и денежные `delta`.

### `app/services/blackjack_repository.py`

Единый transactional adapter между state machine и БД.

## Поток данных: player action

1. API view парсит запрос.
2. Accessor загружает `BlackjackService`.
3. `BlackjackService.apply_action()` проверяет доступность события.
4. `prepare_event` строит runtime context.
5. Validators и guards выбирают переход.
6. `apply_player_move` вызывает dispatcher.
7. Repository сохраняет side effects.
8. Если требуется, автоматически выполняются dealer turn и settlement.
9. Возвращается snapshot сессии.

## Поток данных: timeout / single_stop

### Timeout

Timeout проходит через state machine событие `timeout_turn`, а затем, при необходимости, через обычный dealer+settlement pipeline.

### Single stop

Bot-facing `single_stop` использует ту же доменную ветку, что и `stand`, поэтому:
- сохраняется единая игровая семантика;
- нет обхода validators/guards;
- итоговый snapshot выглядит так же, как после обычного `stand`.

## Что где дебажить

- переходы и event availability — `BlackjackService`
- отклонение действия — `turn_rules.py`
- следующий игрок и projected state — `event_context_builder.py`
- конкретный payload действия — `action_dispatch.py`
- поведение дилера — `dealer_policy.py`
- деньги и результаты — `settlement_policy.py`
- запись в БД и audit log — `blackjack_repository.py`
