# Entities And Responsibilities

## ORM entities

### `Player`

- уникальный `telegram_id`
- текущий `bank`
- флаг бана

### `Deck`

- логический chat context по `chat_id`
- JSON `meta`

### `GameSession`

- FK на `deck_id`
- persisted lifecycle status
- `dealer_cards`, `current_position`, `current_timer`
- `count_players`, `dealer_bet`

### `PlayerToSession`

- позиция игрока за столом
- ставка и карты руки
- participant status

### `State`

- immutable audit log для значимых игровых переходов
- хранит `action`, `position`, `details`, timestamp

## Accessors

### `CatalogAccessor`

Используется для CRUD-like сценариев: игроки, deck, сессии, посадка игрока.

### `BlackjackAccessor`

Работает с runtime API по `session_id`:
- start session
- apply action
- timeout
- read state

### `BotGameAccessor`

Работает с bot-facing flows по `chat_id`:
- group open/join/start/stop
- single start/stop
- current/last snapshot
- timeout and player actions
- admin operations

## Service layer

### `BlackjackService`

Главный orchestration слой state machine. Делегирует:
- validators и turn branching в domain;
- repository writes в persistence слой;
- расчет dealer/settlement в policy objects.

### `BlackjackRepository`

Загружает runtime context и пишет side effects в БД транзакционно.

### `BlackjackSessionContext` и `PlayerSlotSnapshot`

In-memory проекция состояния, с которой работает state machine.

## Domain layer

### `turn_rules.py`

Валидирует старты, действия, timeout и выбор следующего playable игрока.

### `event_context_builder.py`

Собирает projected runtime context для validators, guards и action callbacks.

### `action_dispatch.py`

Преобразует `hit/stand/double/split/insurance` в единый persistence-ready payload.

### `dealer_policy.py`

Управляет добором карт дилера до stop threshold.

### `settlement_policy.py`

Строит `result` и `delta` для каждого игрока.

## Время и таймеры

Сервис использует `utc_now_naive()` для совместимости с БД-колонками без timezone. `current_timer` хранится на уровне сессии и проверяется при timeout-обработке.
