# Poller Service Docs

Навигация по документации `poller`.

## Что описано

- long polling lifecycle;
- offset persistence и contiguous commit semantics;
- Kafka envelope contract;
- bounded queues, worker pool и graceful shutdown.

## Карта документов

- [service_overview.md](service_overview.md) — роль сервиса, зависимости и ключевые runtime модули.
- [entities.md](entities.md) — `QueuedUpdate`, `TelegramUpdateEnvelope`, `OffsetCommitTracker`, `OffsetStore`, `UpdateSink`.
- [runtime_lifecycle.md](runtime_lifecycle.md) — startup, main loop, error handling, shutdown.

## Связанные файлы

- [../README.md](../README.md)
- `../app/main.py`
- `../app/runtime/`
- `../app/downstream/`
- `../app/storage/offset_store.py`
