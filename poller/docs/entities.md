# Poller Entities And Contracts

## Основные сущности

## 1. Telegram update

Сырой объект от Telegram Bot API.

Ключевые поля:
- `update_id`
- один из top-level payload ключей (`message`, `callback_query`, ...)

Используется как источник для envelope и расчета offset.

## 2. QueuedUpdate (`app/runtime/intake_queue.py`)

Внутренняя runtime-сущность очередей.

Поля:
- `sequence_number` — локальная последовательность для commit tracker
- `update` — сырой update
- `next_offset` — ожидаемый offset после обработки

Нужна, чтобы отслеживать порядок ack независимо от параллельной обработки.

## 3. TelegramUpdateEnvelope (`app/downstream/contracts.py`)

Контракт сообщения для Kafka.

Поля:
- `update_id: int`
- `update_type: str`
- `source_key: str`
- `partition_key: str`
- `next_offset: int`
- `received_at: datetime`
- `payload: dict`

## 4. OffsetStore (`app/storage/offset_store.py`)

Абстракция хранения offset.

Операции:
- `load_offset()`
- `save_offset(offset)`

Базовая реализация: `FileOffsetStore`.

## 5. UpdateSink (`app/downstream/sink.py`)

Downstream-абстракция доставки update.

Операция:
- `handle(update)`

Базовая реализация: `KafkaUpdateSink`.

## 6. OffsetCommitTracker (`app/runtime/ack_tracker.py`)

Служебная сущность для contiguous commit:
- помечает обработанные sequence
- возвращает максимальный непрерывный committable offset

## 7. QueueBackpressureMonitor (`app/runtime/backpressure.py`)

Метрики и контроль заполненности очередей ingress/worker.

## Поток сущностей

`Telegram update` -> `QueuedUpdate` -> `TelegramUpdateEnvelope` -> `Kafka topic`
