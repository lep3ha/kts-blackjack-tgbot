# Poller Runtime Lifecycle

## Startup

1. Загружаются `Settings`.
2. Создаются `TelegramPollingClient`, `OffsetStore`, `UpdateSink`.
3. Инициализируется `PollingRunner`.
4. Поднимаются внешние ресурсы, в том числе Kafka producer.
5. Загружается последний сохраненный offset.

## Main loop

1. Producer делает `getUpdates(offset=last_confirmed_offset)`.
2. Каждый update получает локальный `sequence_number` и попадает в ingress queue.
3. Dispatcher раскладывает update по worker queues через partitioning strategy.
4. Worker публикует envelope в sink.
5. После успешной публикации worker отмечает sequence в `OffsetCommitTracker`.
6. Когда tracker видит непрерывный префикс завершенных sequence, новый offset сохраняется в `OffsetStore`.

## Error handling

- `RetryableTelegramError` -> backoff и повторный polling.
- `FatalTelegramError` -> остановка runtime.
- ошибка sink/worker -> offset для проблемного update не подтверждается.
- ошибка мониторинга/runtime task -> fail-fast shutdown, чтобы не продолжать работу в полуразрушенном состоянии.

## Shutdown

1. Producer прекращает прием новых update.
2. Закрывается ingress queue.
3. Dispatcher дренирует уже принятые update в worker queues.
4. Worker pool завершает отправку накопленных элементов.
5. Закрываются monitoring tasks и ресурсы sink.

## Гарантии

1. At-least-once delivery.
2. Нет преждевременного offset commit поверх необработанных сообщений.
3. Graceful shutdown не теряет уже принятые update, если процесс доходит до нормального завершения.
