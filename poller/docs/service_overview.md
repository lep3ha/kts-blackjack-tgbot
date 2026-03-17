# Poller Service Overview

## Назначение

`poller` изолирует работу с Telegram Bot API и гарантирует публикацию update в Kafka с at-least-once semantics.

## Внешние зависимости

- Telegram Bot API
- Kafka/Redpanda
- локальная файловая система для offset state

## Основные обязанности

- выполнять `getUpdates` с текущим offset;
- назначать каждому update локальный sequence number;
- публиковать `TelegramUpdateEnvelope` в Kafka;
- подтверждать offset только после contiguous ack.

## Ключевые runtime модули

- `app/telegram/client.py` — polling client и retry policy
- `app/runtime/runner.py` — общий orchestrator runtime цикла
- `app/runtime/producer.py` — long polling producer
- `app/runtime/dispatcher.py` — ingress -> worker queues
- `app/runtime/consumer.py` — worker publish + commit flow
- `app/runtime/ack_tracker.py` — contiguous sequence tracking
- `app/runtime/backpressure.py` — queue fill monitoring
- `app/runtime/monitoring.py` — fail-fast supervision
- `app/storage/offset_store.py` — atomic file-based offset persistence
- `app/downstream/kafka.py` — Kafka producer wrapper

## Публикационный контракт

Каждый update превращается в `TelegramUpdateEnvelope` с полями:
- `schema_version`
- `event_name`
- `update_id`
- `update_type`
- `source_key`
- `partition_key`
- `next_offset`
- `received_at`
- `payload`

`partition_key` используется для устойчивого downstream partitioning по источнику update.

## Надежность

1. Offset сохраняется только после подтвержденной публикации.
2. При параллельной обработке подтверждается только contiguous sequence.
3. При падении worker offset не продвигается поверх «дырки».
4. На graceful shutdown сервис сначала прекращает прием, затем дренирует очереди.
