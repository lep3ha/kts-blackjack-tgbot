# Orchestrator Service Docs

Навигация по документации `orchestrator`.

## Что описано

- consume flow от Kafka до Telegram ответа;
- Redis context, dedup и timer architecture;
- normalization, local guards, cleanup и timeout semantics.

## Карта документов

- [service_overview.md](service_overview.md) — роль сервиса, ключевые модули и интеграции.
- [entities.md](entities.md) — команды, результаты, Redis session context и timer entities.
- [command_flow.md](command_flow.md) — end-to-end пайплайн обработки команд и ошибок.

## Связанные файлы

- [../README.md](../README.md)
- `../app/main.py`
- `../app/routing/`
- `../app/sender/`
- `../app/state/`
- `../app/timers/`