# Poller Entities And Contracts

## `Telegram update`

Сырой объект Telegram Bot API. Используется как источник для envelope и для вычисления `next_offset = update_id + 1`.

## `QueuedUpdate`

Runtime-объект между producer, dispatcher и worker pool.

Ключевые поля:
- `sequence_number`
- `update`
- `next_offset`

`sequence_number` нужен потому, что worker processing может быть параллельным, а offset commit должен оставаться contiguous.

## `TelegramUpdateEnvelope`

Kafka contract из `app/downstream/contracts.py`.

Поля:
- `schema_version`
- `event_name`
- `update_id`
- `update_type`
- `source_key`
- `partition_key`
- `next_offset`
- `received_at`
- `payload`

## `OffsetStore`

Абстракция чтения/записи подтвержденного offset.

Основная реализация — `FileOffsetStore`, который:
- читает JSON offset state;
- сохраняет файл атомарно через временный файл и replace.

## `UpdateSink`

Интерфейс downstream доставки update. Основная реализация — `KafkaUpdateSink`.

## `OffsetCommitTracker`

Хранит отмеченные как обработанные sequence numbers и выдает только максимальный непрерывный committable offset.

Пример:
- обработаны sequence `1`, `2`, `5`
- `3` и `4` еще не подтверждены
- commit возможен только до offset, связанного с `2`

## `QueueBackpressureMonitor`

Следит за заполнением ingress и worker queues и помогает не потерять контроль над нагрузкой.
