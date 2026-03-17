# Poller Service

`poller` получает update из Telegram Bot API через long polling и публикует их в Kafka topic `telegram.updates.raw`.

## Ответственность сервиса

Сервис отвечает за:
- long polling и retry к Telegram API;
- преобразование update в `TelegramUpdateEnvelope`;
- публикацию в Kafka/Redpanda;
- сохранение offset только после подтвержденной downstream-доставки.

Сервис не отвечает за:
- интерпретацию игровых команд;
- работу с Redis и игровым состоянием;
- отправку пользовательских ответов в Telegram.

## Быстрый старт

Полный стек:

```bash
docker compose up --build
```

Локально только `poller`:

```bash
python -m pip install -r requirements.txt
python run.py
```

## Основные настройки

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BASE_URL`
- `TELEGRAM_POLL_TIMEOUT`
- `TELEGRAM_POLL_LIMIT`
- `TELEGRAM_REQUEST_TIMEOUT`
- `TELEGRAM_RETRY_BASE_DELAY`
- `TELEGRAM_RETRY_MAX_DELAY`
- `OFFSET_STATE_PATH`
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_TOPIC_UPDATES`
- `KAFKA_CLIENT_ID`
- `KAFKA_REQUIRED_ACKS`
- `WORKER_COUNT`
- `MAX_IN_FLIGHT_UPDATES`
- `SHUTDOWN_TIMEOUT`

## Надежность

- offset подтверждается только после успешной публикации в sink;
- используется contiguous ack tracking по локальным sequence numbers;
- bounded queues ограничивают нагрузку;
- graceful shutdown дренирует ingress и worker queues.

## Тесты

```bash
python -m pytest -q
```

## Документация

- [docs/README.md](docs/README.md)
- [docs/service_overview.md](docs/service_overview.md)
- [docs/entities.md](docs/entities.md)
- [docs/runtime_lifecycle.md](docs/runtime_lifecycle.md)

## Автор

- ФИО: Югай Александр Леонидович
- Telegram: @lep3ha
- Email: alexandr.youguy@gmail.com
