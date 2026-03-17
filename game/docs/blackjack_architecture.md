# Архитектура Blackjack После Рефакторинга

## Цель Разделения
Новая структура делит систему на независимые части:
- orchestration переходов state machine,
- доменные правила и стратегии,
- подготовка runtime-контекста событий,
- dispatch действий игрока в единый формат для persistence,
- сохранение состояния в БД.

Главный эффект: проще дебажить, проще расширять правила, меньше связности между слоями.

## Модули И Ответственности

### 1. `app/services/blackjack_service.py`
Роль: оркестратор state machine.

Что делает:
- объявляет состояния и переходы (`waiting -> dealing -> player_turn -> dealer_turn -> resolving -> closed`),
- обрабатывает публичные операции (`start_session`, `apply_action`, `handle_timeout`),
- управляет транзакцией (`commit`/`rollback`),
- проверяет доступность событий,
- запускает авто-дренаж терминальных фаз (`dealer_turn`, `resolving`).

Что больше не делает напрямую:
- не содержит детальные правила действий игрока,
- не содержит ветвление `hit/stand/double` в apply-логике,
- не строит runtime-контекст вручную.

### 2. `app/domain/blackjack/turn_rules.py`
Роль: правила хода игрока и валидация.

Что делает:
- `validate_can_start` проверяет возможность старта,
- `validate_player_move` проверяет корректность действия,
- `validate_timeout_request` проверяет корректность timeout,
- решает, может ли рука еще ходить,
- определяет, кто следующий активный игрок,
- содержит условия ветвления (`keeps_same_turn`, `advances_to_next_player`, `advances_to_dealer`).

### 3. `app/domain/blackjack/event_context_builder.py`
Роль: построение runtime-контекста события для callback-ов state machine.

Что делает:
- резолвит `position` и `action` (включая `timeout_turn -> timeout`),
- находит активного игрока (`seat`),
- моделирует projected-состояние руки (`projected_cards`, `projected_score`),
- определяет `next_position`,
- возвращает единый словарь для validators/conditions/actions.

Плюс: теперь логика подготовки события централизована и тестируется отдельно от сервиса.

### 4. `app/domain/blackjack/action_dispatch.py`
Роль: единый dispatch действий игрока.

Ключевые типы:
- `ActionRuntimeContext`: входные данные на момент dispatch,
- `ActionDispatchResult`: итог для repository (`cards`, `bet`, `next_position`, `details`, `should_schedule_timer`),
- `PlayerActionDispatcher`: роутер action -> handler (`hit`, `stand`, `double`).

Что делает:
- переводит доменный контекст в persistence-ready payload,
- унифицирует формирование `details` журнала,
- убирает ветвление действий из `BlackjackService.apply_player_move`.

### 5. `app/domain/blackjack/dealer_policy.py`
Роль: стратегия дилера.

Что делает:
- добор карт до порога `stand_score`,
- возвращает итоговые карты дилера и список добранных карт.

### 6. `app/domain/blackjack/settlement_policy.py`
Роль: расчет исходов раунда и выплат.

Что делает:
- считает `result` и `delta` для каждого игрока,
- возвращает settlement-список для repository.

### 7. `app/domain/blackjack/settings.py`
Роль: служебные настройки runtime-логики.

Что хранит:
- набор разрешенных действий игрока,
- порог остановки дилера.

Идея: фичи и поведенческие флаги живут отдельно от state machine-графа и persistence-модели.

### 8. `app/services/blackjack_repository.py`
Роль: транзакционное сохранение состояния.

Что делает:
- загружает контекст сессии,
- сохраняет эффекты раздачи, действий, timeout, хода дилера, settlement,
- пишет журнал `states`.

## Поток Данных: `PUT /sessions/{id}/actions`
1. API вызывает accessor.
2. Accessor загружает `BlackjackService` через `load()`.
3. `apply_action(position, action)` в сервисе:
- проверка доступности события `player_move`,
- запуск transition.
4. Внутри transition:
- `prepare_event` вызывает `EventContextBuilder.build`,
- validators/conditions используют данные из контекста,
- `apply_player_move` вызывает `PlayerActionDispatcher.dispatch`.
5. Сервис передает нормализованный payload в `BlackjackRepository.persist_player_move`.
6. Если после хода наступил `dealer_turn`/`resolving`, `_drain_terminal_phases` доигрывает раунд автоматически.
7. На успехе транзакция коммитится, на ошибке откатывается.

## Поток Данных: `PUT /sessions/{id}/timeout`
1. Сервис проверяет доступность `timeout_turn`.
2. `prepare_event` через builder формирует контекст timeout.
3. `validate_timeout_request` из `PlayerTurnRules` проверяет корректность.
4. `apply_timeout` сохраняет эффект через repository.
5. Затем выполняется авто-дренаж дилера/резолва, если применимо.

## Где Дебажить Конкретные Проблемы
- Неверные переходы state machine:
  - `BlackjackService._ensure_event_available`, `_build_transition_error`.
- Почему действие игрока отклонено:
  - `PlayerTurnRules.validate_player_move`.
- Почему timeout не сработал:
  - `PlayerTurnRules.validate_timeout_request` и `BlackjackService._timer_expired`.
- Почему после действия выбрана конкретная next-позиция:
  - `EventContextBuilder.build` + `PlayerTurnRules.next_playable_position`.
- Почему `hit/stand/double` дали такой payload:
  - `PlayerActionDispatcher.dispatch` и соответствующий handler.
- Почему дилер взял/не взял карту:
  - `DealerPolicy.play_turn`.
- Почему такой settlement:
  - `SettlementPolicy.build_settlements`.

## Как Добавлять Новое Правило Или Действие
1. Добавить action в `settings.py`.
2. Добавить handler в `PlayerActionDispatcher`.
3. Обновить валидацию/ветвление в `PlayerTurnRules`.
4. При необходимости обновить `EventContextBuilder` (если нужен новый контекст).
5. Если меняются выплаты, обновить `SettlementPolicy`.
6. Если меняется поведение дилера, обновить `DealerPolicy`.
7. Обновить тесты и документацию.

Такой путь удерживает `BlackjackService` тонким и предотвращает рост сложности при дальнейшем расширении правил.
