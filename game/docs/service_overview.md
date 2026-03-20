# Game Service Overview

## Назначение

`game` — доменный HTTP-сервис blackjack. Он принимает команды от `orchestrator`, применяет правила игры, пишет состояние в PostgreSQL и возвращает канонический snapshot сессии.

## Зона ответственности

Сервис делает:
- lifecycle single и group сессий;
- обработку `hit`, `stand`, `double`, `split`, `insurance`, `timeout`, bot stop-сценариев;
- расчет дилера и settlement;
- bot-facing и debug/runtime HTTP API.

Сервис не делает:
- чтение Telegram update;
- отправку ответов пользователю;
- dedup, Redis-context и таймерные очереди transport-уровня.

## Архитектурные слои

### API

- `app/api/` и `app/api/views/`
- class-based views и единый error middleware
- `/openapi.json` строится из swagger metadata

### Accessors

- `CatalogAccessor` — CRUD-like операции с игроками, deck и сессиями
- `BlackjackAccessor` — runtime операции по `session_id`
- `BotGameAccessor` — bot-facing операции по `chat_id` и `actor_telegram_id`

### Domain / State Machine

- `BlackjackService` — orchestration state machine
- `turn_rules.py` — validators и branching logic
- `dealer_policy.py` — поведение дилера
- `settlement_policy.py` — расчет результата и `delta`
- `event_context_builder.py` и `action_dispatch.py` — подготовка runtime payload

### Persistence

- `BlackjackRepository` — transactional writes
- PostgreSQL + Alembic
- audit trail в таблице `states`

## Интеграции

- PostgreSQL — основное хранилище
- `orchestrator` — основной HTTP-клиент сервиса

## Ключевые инварианты

1. Каждая публичная операция выполняется транзакционно: success -> commit, error -> rollback.
2. Snapshot сессии после пользовательского действия уже отражает auto-drain terminal phases.
3. `turn_version` защищает от устаревших действий и timeout-задач.
4. История значимых переходов пишется в `states`.

## Особенности bot-facing семантики

- `single_stop` эквивалентен `stand` активного игрока, а не shortcut settlement.
- `group player stop` выводит конкретного игрока из активной групповой игры.
- timeout для текущего игрока допустим только после истечения `current_timer`.
