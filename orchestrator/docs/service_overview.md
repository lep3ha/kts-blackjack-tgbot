# Orchestrator Service Overview

## Назначение

`orchestrator` преобразует транспортные Telegram update в игровые команды и обратно в Telegram UX-ответы.

## Внешние зависимости

- Kafka/Redpanda
- Redis
- `game` HTTP API
- Telegram Bot API

## Основные обязанности

- consume `telegram.updates.raw` из Kafka;
- нормализовать slash commands, reply buttons и callback data;
- вызывать `game` handlers через HTTP client;
- рендерить сообщения и клавиатуры;
- хранить session context, dedup keys и turn timers в Redis.

## Ключевые модули

- `app/main.py` — сборка приложения, регистрация команд и wiring
- `app/routing/normalizer.py` — message/callback -> command
- `app/routing/pipeline.py` — orchestration полного command flow
- `app/routing/handlers/` — game API handlers, local guards и admin flows
- `app/sender/presenter.py` — форматирование текстов и клавиатур
- `app/sender/client.py` — Telegram send/delete/setMyCommands
- `app/state/` — Redis dedup/context store
- `app/timers/redis_worker.py` — scheduling/claiming timeout tasks
- `app/timers/executor.py` — timeout -> game call -> Telegram notice

## Что важно в runtime

1. Local guards режут часть ошибок до HTTP round-trip в `game`.
2. Reply UX зависит от `SessionContext.reply_action_hint`.
3. Cleanup предыдущего game-state сообщения зависит от результата и текущего игрока.
4. Timeout worker использует Redis keys для retention, claim и done semantics.
