# Poller Service Overview

## Назначение

`poller` изолирует работу с Telegram Bot API и гарантирует доставку входящих update в Kafka topic `telegram.updates.raw`.

Сервис решает три задачи:
- устойчивый long polling с retry
- безопасный commit offset только после подтвержденной публикации
- контроль нагрузки через bounded queues и worker pool

## Границы ответственности

`poller` делает:
- читает Telegram updates (`getUpdates`)
- нормализует их в broker envelope
- публикует в Kafka
- сохраняет offset в локальном storage

`poller` не делает:
- не интерпретирует игровые команды
- не хранит сессионный state игры
- не отправляет игровые ответы в Telegram

## Внешние зависимости

- Telegram Bot API
- Kafka/Redpanda
- локальная файловая система для offset state

## Ключевые модули

- `app/telegram/client.py` — HTTP-клиент Telegram + retry policy
- `app/runtime/runner.py` — orchestration polling loop, partitioning, workers
- `app/downstream/kafka.py` — публикация envelope в Kafka
- `app/storage/offset_store.py` — файловое сохранение offset
- `app/downstream/envelope.py` — сборка контракта сообщения для брокера

## Контракт публикации

Каждый update публикуется как envelope с полями:
- `update_id`
- `update_type`
- `source_key`
- `partition_key`
- `next_offset`
- `received_at`
- `payload`

`partition_key` и `source_key` синхронизируют порядок обработки по источнику (chat/user) в downstream сервисах.

## Надежность и завершение

- offset сохраняется только после успешной downstream-публикации
- на shutdown выполняется drain ingress/worker очередей
- при аварии runtime-таски корректно отменяются, offset не продвигается по недоставленным событиям
