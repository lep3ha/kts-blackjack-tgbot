# Router Service Docs

Документация для микросервиса `router` (маршрутизация Telegram-команд между Kafka, Redis, Telegram Bot API и `game`).

## Что делает сервис

- читает обновления из Kafka (`telegram.updates.raw`)
- нормализует update в `RouterCommand`
- вызывает HTTP API `game`
- рендерит сообщения/клавиатуры и отправляет их в Telegram
- хранит dedup и контекст сессий в Redis

## Пайплайн обработки

```
KafkaUpdatesConsumer
  -> DeduplicatingCommandProcessor
    -> TelegramUpdateNormalizer
    -> RouterCommandDispatcher
    -> GameCommandHandlers
    -> RouterResultPresenter
    -> TelegramSenderClient
    -> RedisSessionContextStore
```

## Карта документации

- `service_overview.md` — архитектурная роль сервиса, границы ответственности и интеграции.
- `entities.md` — ключевые сущности и ответственности (`RouterCommand`, `RouterResult`, `SessionContext`, dedup/timer entities).
- `command_flow.md` — end-to-end пайплайн обработки команд, ошибки и таймеры.

## Связанные файлы

- `../README.md` — запуск и разработка router-сервиса.
- `../app/routing/` — нормализация, диспетчеризация, пайплайн.
- `../app/sender/` — presenter и Telegram-клиент.