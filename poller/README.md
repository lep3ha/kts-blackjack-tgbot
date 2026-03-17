# Poller Service

`poller` получает обновления из Telegram Bot API (long polling) и публикует их в Kafka topic `telegram.updates.raw`.

## Назначение

- читать входящие update от Telegram
- сохранять offset
- передавать события в Kafka для дальнейшей обработки в `router`

## Запуск в полном стеке

Из корня проекта:

```bash
docker compose up --build
```

## Локальный запуск сервиса

```bash
python -m pip install -r requirements.txt
python run.py
```

## Дополнительная документация

См. [docs/README.md](docs/README.md).

## Автор

- ФИО: Югай Александр Леонидович
- Telegram: @lep3ha
- Email: alexandr.youguy@gmail.com
