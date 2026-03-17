# Доменные Сущности И Ответственности

## ORM-Сущности (`app/models/__init__.py`)

1. `Player`
- Идентификатор: `id`.
- Внешний идентификатор: `telegram_id` (уникальный).
- Изменяемое поле: `bank`.
- Временная метка: `created_at`.

2. `Deck`
- Идентификатор: `id`.
- Внешний идентификатор: `chat_id` (уникальный).
- `meta` JSON для метаданных комнаты/колоды.
- Временная метка: `created_at`.

3. `GameSession`
- Идентификатор: `id`.
- FK: `deck_id -> Deck.id`.
- Persisted lifecycle-статус (`SessionStatus`): `lobby_open|in_progress|stopped|closed`.
- Runtime-поля: `dealer_cards`, `current_position`, `current_timer`.
- Конфигурационные поля: `count_players`, `dealer_bet`.
- Временная метка: `created_at`.

4. `PlayerToSession`
- Связь места игрока с игровой сессией.
- Поля: `position`, `bet`, `cards`.
- Ограничения:
  - unique `(session_id, position)`
  - проверка диапазона позиции `1..8`

5. `State`
- Неизменяемая запись журнала событий.
- Поля: `session_id`, `position`, `action`, `time`, `details`.
- Проверка диапазона позиции `1..8`.

## Access-Слой (`app/accessors`)

1. `CatalogAccessor`
- Отвечает за CRUD-подобные сценарии:
  - create player
  - create deck
  - create session
  - seat player
- Выполняет проверки целостности и бизнес-правил до `commit`.

2. `BlackjackAccessor`
- Отвечает за runtime-сценарии игры:
  - start session
  - apply action
  - force timeout
  - read state
- Преобразует сервисный контекст в DTO ответа API.

## Service-Слой (`app/services`)

1. `BlackjackService`
- Оркестрация state machine и управление транзакционным жизненным циклом операций.
- Публичные методы:
  - `start_session()`
  - `apply_action(position, action)`
  - `handle_timeout(position)`
  - `available_events()`

Основное после рефакторинга:
- сервис делегирует валидацию и ветвление в доменные правила,
- сервис делегирует подготовку event payload в builder,
- сервис делегирует разбор действия игрока в dispatcher,
- сервис сам не хранит детализацию `hit/stand/double`.

2. `BlackjackRepository`
- Транзакционный адаптер персистентности для callback-ов state machine.
- Загружает снимок `BlackjackSessionContext`.
- Сохраняет изменения фаз и события журнала.

3. `BlackjackSessionContext` / `PlayerSlotSnapshot`
- In-memory runtime-проекция, которую использует state machine.
- Содержит поля, необходимые для guard-условий и callback-ов переходов.

Примечание:
- Runtime state machine state (например, `waiting/dealing/player_turn`) не равен persisted `SessionStatus`.
- `BlackjackSessionContext` и `PlayerSlotSnapshot` определены в `app/domain/blackjack/context.py`.

## API-Слой (`app/api`)

- Class-based view наследуются от `BaseView`.
- Middleware маппит доменные исключения в единый формат ошибки.
- Swagger-метаданные методов собираются в `/openapi.json`.

## Domain-Слой (`app/domain/blackjack`)

1. `settings.py`
- Конфигурация служебных runtime-параметров:
  - разрешенные действия игрока,
  - порог остановки дилера.

2. `turn_rules.py`
- Валидация и ветвление хода игрока:
  - старт сессии,
  - player move,
  - timeout,
  - выбор следующей активной позиции,
  - условия переходов state machine.

3. `event_context_builder.py`
- Построение единого runtime-контекста для события state machine:
  - `position`, `action`, `seat`, `projected_cards`, `projected_score`, `next_position`.

4. `action_dispatch.py`
- Единый dispatch действий игрока (`hit`, `stand`, `double`) в persistence-ready формат:
  - итоговые карты,
  - ставка,
  - следующая позиция,
  - флаг таймера,
  - `details` для журнала.

5. `dealer_policy.py`
- Правило поведения дилера (добор и остановка).

6. `settlement_policy.py`
- Расчет исходов (`result`) и дельт баланса (`delta`) для каждого игрока.

## Работа Со Временем

- Сервис использует helper `utc_now_naive()` из `app/core/datetime_utils.py`.
- Helper возвращает UTC-время без `tzinfo`, чтобы оставаться совместимым с текущими колонками `DateTime` (`timestamp without time zone`) и при этом избегать deprecation warning для `datetime.utcnow()`.
