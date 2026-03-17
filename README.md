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

| Команда | Действие |
|---|---|
| `/start` | Туториал с кнопкой «Начать игру» |
| `/single_start` | Одиночная игра (личный чат) |
| `/group_start` | Открыть групповое лобби |
| `/start_round` | Запустить раунд в лобби |
| `/join` | Присоединиться к лобби |
| `/current` | Текущее состояние сессии |
| `/stop` | Остановить одиночную игру |
| `/admin_topup` | Пополнить баланс игрока (по telegram_id) |
| `/admin_ban` | Забанить игрока (по telegram_id) |

## Автор

- ФИО: Югай Александр Леонидович
- Telegram: @lep3ha
- Email: alexandr.youguy@gmail.com

