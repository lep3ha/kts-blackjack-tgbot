# Router Entities And Responsibilities

## 1. TelegramUpdateEnvelope (`app/upstream/contracts.py`)

Входной контракт события из Kafka.

Ключевые поля:
- `update_id`
- `update_type`
- `source_key`
- `partition_key`
- `next_offset`
- `received_at`
- `payload`

## 2. RouterCommand (`app/routing/models.py`)

Нормализованная команда для бизнес-обработки.

Ключевые поля:
- `chat_id`, `chat_type`
- `actor_telegram_id`, `actor_username`
- `command_type`
- `bet`, `action`, `turn_version`
- `admin_target_username`

## 3. RouterResult (`app/routing/models.py`)

Результат обработки команды.

Поля:
- `success`
- `message`
- `command_type`
- `error_code`
- `data`

Используется presenter-слоем для формирования Telegram-ответа.

## 4. SessionContext (`app/state/models.py`)

Контекст чата/сессии в Redis.

Хранит:
- последний `message_id` для cleanup
- контекст UX-маршрутизации (`reply_action_hint`)
- служебные поля для устойчивой обработки команд

## 5. DedupStore (`app/state/interfaces.py`)

Абстракция защиты от повторной обработки update.

Базовая реализация:
- `RedisDedupStore`

## 6. Timer worker entities (`app/timers/models.py`)

Сущности timeout-планирования:
- задача таймера
- claim/lease метаданные
- состояние выполнения timeout callback

## Поток сущностей

`TelegramUpdateEnvelope` -> `RouterCommand` -> `RouterResult` -> Telegram outbound message
