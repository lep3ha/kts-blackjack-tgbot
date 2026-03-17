# Poller Service Docs

Документация для микросервиса `poller` (Telegram long polling и публикация событий в Kafka).

## Что делает сервис

- читает обновления из Telegram Bot API
- хранит и продвигает offset
- публикует нормализованные envelopes в Kafka (`telegram.updates.raw`)

## Карта документации

- `service_overview.md` — архитектурная роль сервиса, границы ответственности, интеграции.
- `entities.md` — ключевые runtime-сущности и контракты (`QueuedUpdate`, `TelegramUpdateEnvelope`, `OffsetStore`, `UpdateSink`).
- `runtime_lifecycle.md` — startup/main-loop/error-handling/shutdown и инварианты надежности.

## Связанные файлы

- `../README.md` — запуск и разработка poller-сервиса.
- `../app/main.py` — сборка runtime-компонентов.
