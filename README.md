# Blackjack Telegram Bot

Telegram-бот для игры в блэкджек — одиночный и групповой режим.

## Ссылка на бота

https://t.me/blackjack_by_lep3ha_bot

## Архитектура

```
Telegram ──► poller ──► Kafka ──► router ──► game ──► PostgreSQL
                                     │
                                   Redis (сессии, дедупликация, таймеры)
```

| Сервис | Описание |
|---|---|
| `poller` | Long-polling от Telegram API, публикует обновления в Kafka |
| `router` | Kafka-consumer: нормализует команды, маршрутизирует в `game`, отправляет ответы в Telegram |
| `game` | HTTP API игры (aiohttp + PostgreSQL + Alembic) |
| `db` | PostgreSQL 15 |
| `redis` | Контекст сессий, дедупликация сообщений, таймеры ходов |
| `redpanda` | Kafka-совместимый брокер |

## Запуск

```bash
docker compose up --build
```

Все сервисы запустятся автоматически. При первом старте `game` применяет миграции Alembic.

### Переменные окружения

| Файл | Что задаёт |
|---|---|
| `poller/.env` | `TELEGRAM_TOKEN`, `KAFKA_BOOTSTRAP_SERVERS` |
| `router/.env` | `TELEGRAM_TOKEN`, `KAFKA_BOOTSTRAP_SERVERS`, `REDIS_URL`, `GAME_BASE_URL` |
| `game/.env` | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` |

### Порты (localhost)

| Порт | Сервис |
|---|---|
| `8001` | game HTTP API |
| `5433` | PostgreSQL |
| `6379` | Redis |
| `19092` | Redpanda (Kafka external) |

## Сборка

`poller` и `router` собираются из корневого `Dockerfile` (multi-stage targets `poller-runtime` и `router-runtime`).  
`game` собирается из `game/Dockerfile`.

## Команды бота

| Команда | Аргументы | Действие |
|---|---|---|
| `/start` | нет | Туториал с кнопкой «Начать игру» |
| `/single_start` | `[bet]` | Одиночная игра в личном чате |
| `/create_lobby` | `<bet>` | Открыть групповое лобби для подключения игроков |
| `/group_start` | нет | Запустить уже открытое лобби |
| `/join` | `<bet>` | Присоединиться к открытому групповому лобби |
| `/current` | нет | Показать текущее состояние сессии |
| `/stop` | нет | В личке завершает single-сессию, в группе переводит игрока в неактивное состояние |
| `/admin_topup` | `<username> <amount>` | Пополнить баланс игрока |
| `/admin_ban` | `<username>` | Забанить игрока |
| `/start_round` | нет | Legacy alias для `/group_start` |

В группах поддерживается Telegram-формат команд с mention бота, например:
- `/start@blackjack_by_lep3ha_bot`
- `/create_lobby@blackjack_by_lep3ha_bot 200`
- `/group_start@blackjack_by_lep3ha_bot`

## Автор

- ФИО: Югай Александр Леонидович
- Telegram: @lep3ha
- Email: alexandr.youguy@gmail.com

