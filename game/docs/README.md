# Game Service Docs

Навигация по документации микросервиса `game`.

## Что покрывает документация

- HTTP API и коды ошибок;
- state machine и runtime lifecycle раунда;
- доменные правила blackjack;
- bot-facing сценарии single/group/admin;
- устройство persistence и доменных сущностей.

## Карта документов

- [service_overview.md](service_overview.md) — роль сервиса в системе, слои и зависимости.
- [api.md](api.md) — актуальный HTTP API, форматы ответов и bot-facing ручки.
- [game_logic.md](game_logic.md) — игровые правила, timeout и settlement семантика.
- [state_machine.md](state_machine.md) — runtime states, validators, guards и auto-drain phases.
- [entities.md](entities.md) — ORM, runtime context, repository и bot accessors.
- [blackjack_architecture.md](blackjack_architecture.md) — поток данных и структура модулей после рефакторинга.

## Связанные файлы

- [../README.md](../README.md) — запуск и разработка сервиса.
- `../app/api/views/` — HTTP views.
- `../app/accessors/` — catalog/runtime/bot accessors.
- `../app/services/blackjack_service.py` — state machine orchestration.
- `../alembic/` — миграции БД.
