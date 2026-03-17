# Router Service Overview

## Назначение

`router` преобразует входящие Telegram updates в бизнес-команды и связывает transport-уровень с игровым API.

Сервис решает задачи:
- потребление обновлений из Kafka
- нормализация в `RouterCommand`
- вызовы `game` HTTP API через handler-слой
- формирование ответа для Telegram (текст, стикеры, клавиатуры)
- хранение dedup и session context в Redis

## Границы ответственности

`router` делает:
- маршрутизацию команд (`tutorial`, `single_start`, `group_open`, `group_start`, ...)
- anti-duplication обработку update
- управление reply keyboard логикой и contextual hints
- планирование timeout-задач через timer worker

`router` не делает:
- не реализует правила blackjack (это ответственность `game`)
- не хранит долгосрочные игровые данные (БД в `game`)

## Интеграции

- Kafka/Redpanda: входящий поток update envelopes
- Redis: dedup keys, session context, таймеры
- Game service HTTP API: игровые операции
- Telegram Bot API: отправка ответов и регистрация команд

## Ключевые модули

- `app/routing/normalizer.py` — message/callback -> `RouterCommand`
- `app/routing/dispatcher.py` — dispatch по `CommandType`
- `app/routing/handlers.py` — интеграция с `game_client`
- `app/routing/pipeline.py` — orchestration normalize -> process -> send
- `app/sender/presenter.py` — `RouterResult` -> UI-сообщение
- `app/state/redis_store.py` — Redis stores для dedup/context
- `app/timers/redis_worker.py` — timeout worker
