# Router Service

`router` читает события из Kafka, нормализует команды Telegram, вызывает `game` HTTP API и отправляет ответы обратно в Telegram.

## Назначение

- Kafka consumer для `telegram.updates.raw`
- маршрутизация команд в `game`
- формирование текста и клавиатур для ответов
- хранение контекста сессий, дедупликации и таймеров через Redis

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

## Тесты

```bash
python -m pytest -q
```

## Дополнительная документация

См. [docs/README.md](docs/README.md).

## Автор

- ФИО: Югай Александр Леонидович
- Telegram: @lep3ha
- Email: alexandr.youguy@gmail.com
