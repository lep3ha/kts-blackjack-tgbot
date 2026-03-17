# Poller Runtime Lifecycle

## Startup

1. Загружается конфигурация (`Settings`).
2. Инициализируются `TelegramPollingClient`, `OffsetStore`, `UpdateSink`.
3. Создается `PollingRunner`.
4. Инициализируются внешние ресурсы (Kafka producer).

## Main loop

1. `PollingRunner` читает текущий offset.
2. Запускает ingress queue, dispatcher и worker tasks.
3. Выполняет `getUpdates` с текущим offset.
4. Каждое событие кладет в ingress queue как `QueuedUpdate`.
5. Dispatcher маршрутизирует события по worker partition.
6. Worker публикует событие в sink.
7. После успешной публикации commit tracker вычисляет contiguous offset.
8. Committable offset сохраняется в `OffsetStore`.

## Ошибки и retry

- `RetryableTelegramError` -> экспоненциальный backoff по retry policy.
- `FatalTelegramError` -> остановка run-loop.
- Ошибки sink в worker -> offset не подтверждается для проблемного update.

## Shutdown

1. Закрывается ingress queue.
2. Выполняется drain ingress queue.
3. Выполняется drain worker queues.
4. Отменяются runtime monitor tasks.
5. Закрываются ресурсы (`KafkaUpdateSink.close()`).

## Инварианты

- offset не должен сохраняться до подтвержденной downstream-доставки
- порядок подтверждения offset должен быть contiguous
- при частичной обработке в параллельных worker нельзя подтверждать «дырявые» sequence
