    # Blackjack Telegram Bot

Микросервисный Telegram-бот для игры в блэкджек в личных чатах и группах.

## Ссылка на бота

https://t.me/blackjack_by_lep3ha_bot

## Общая архитектура

```
Telegram Bot API
    │
    ▼
poller ──► redpanda(Kafka) ──► orchestrator ──► game ──► PostgreSQL
                                  │
                                  └──────────► Redis
```

### Роли сервисов

| Сервис | Роль |
|---|---|
| `poller` | Делает long polling в Telegram Bot API и публикует update в Kafka topic `telegram.updates.raw`. |
| `orchestrator` | Читает update из Kafka, нормализует команды, вызывает `game`, рендерит ответы и работает с Redis-контекстом, dedup и таймерами. |
| `game` | Хранит игровое состояние и реализует доменную логику blackjack через HTTP API. |
| `db` | PostgreSQL 15 для игровых данных. |
| `redis` | Контекст сессий, dedup ключи и очередь timeout-задач orchestrator. |
| `redpanda` | Kafka-совместимый брокер сообщений. |

## Быстрый старт

```bash
docker compose up --build
```

Что происходит при старте:
1. Поднимаются `db`, `redis`, `redpanda`.
2. `topic-init` создает Kafka topic `telegram.updates.raw`.
3. `game` применяет `alembic upgrade head` и стартует HTTP API.
4. `poller` и `orchestrator` запускаются после готовности инфраструктуры.

## Порты и внешние точки входа

| Порт | Назначение |
|---|---|
| `8001` | `game` HTTP API |
| `5433` | PostgreSQL |
| `6379` | Redis |
| `19092` | Kafka external listener (Redpanda) |
| `18082` | Redpanda PandaProxy |

## Локальная разработка по сервисам

### Game

```bash
cd game
python -m pip install -r requirements.txt
python -m alembic upgrade head
python run.py
```

### Poller

```bash
cd poller
python -m pip install -r requirements.txt
python run.py
```

### Orchestrator

```bash
cd orchestrator
python -m pip install -r requirements.txt
python run.py
```

## Переменные окружения

### Poller

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BASE_URL`
- `TELEGRAM_POLL_TIMEOUT`
- `TELEGRAM_POLL_LIMIT`
- `TELEGRAM_REQUEST_TIMEOUT`
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_TOPIC_UPDATES`
- `OFFSET_STATE_PATH`
- `WORKER_COUNT`
- `MAX_IN_FLIGHT_UPDATES`

### Orchestrator

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BASE_URL`
- `GAME_SERVICE_BASE_URL`
- `GAME_SERVICE_REQUEST_TIMEOUT_SECONDS`
- `REDIS_URL`
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_TOPIC_UPDATES`
- `KAFKA_GROUP_ID`
- `DEDUP_TTL_SECONDS`
- `SESSION_CONTEXT_TTL_SECONDS`
- `TIMER_RETENTION_SECONDS`

### Game

- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `HOST`
- `PORT`
- `BOT_SNAPSHOT_INCLUDE_LEGACY_FIELDS`

## Команды бота

| Команда | Аргументы | Семантика |
|---|---|---|
| `/start` | нет | Показывает краткий туториал и стартовые кнопки. |
| `/single_start` | `[bet]` | Запускает одиночную игру в личном чате. |
| `/create_lobby` | `<bet>` | Открывает групповое лобби. |
| `/group_start` | нет | Стартует уже открытое лобби. |
| `/join` | `<bet>` | Подключает игрока к открытому групповому лобби. |
| `/current` | нет | Возвращает текущее состояние игры. |
| `/stop` | нет | В single режиме делает auto-stand и завершает текущую single-сессию; в group режиме выводит игрока из активного раунда. |
| `/admin_topup` | `<username> <amount>` | Админская команда пополнения баланса. |
| `/admin_ban` | `<username>` | Админская команда блокировки игрока. |
| `/start_round` | нет | Legacy alias для `/group_start`. |

Поддерживаются Telegram-mention варианты команд в группах:
- `/start@blackjack_by_lep3ha_bot`
- `/create_lobby@blackjack_by_lep3ha_bot 200`
- `/group_start@blackjack_by_lep3ha_bot`

## Split Contract (Кратко)

- Действие `split` доступно во время хода игрока через slash/reply/inline UX (`/split`, `Split`, callback).
- Inline payload действий использует формат `action:<move>:tv:<turn_version>[:hand:<hand_index>]`.
- Для message/reply `player_action` без `tv`/`hand` orchestrator наследует `turn_version` и `current_hand_index` из `SessionContext`.
- Post-game действие выполняется inline callback-ами: `session:create:group` (создать новую групповую сессию) и `session:create:single` (начать новую одиночную игру).
- Bot snapshot возвращает split-контекст в `current_hand_index` и `participants[].hands[]` (`hand_index`, `cards`, `bet`, `status`).
- После завершения первой split-руки ход обязан перейти ко второй руке этого же игрока; к дилеру переход только когда активных рук у игрока не осталось.

Детали: `game/docs/api.md`, `game/docs/game_logic.md`, `orchestrator/docs/command_flow.md`, `orchestrator/docs/entities.md`.

## Документация

- [game/README.md](game/README.md)
- [game/docs/README.md](game/docs/README.md)
- [poller/README.md](poller/README.md)
- [poller/docs/README.md](poller/docs/README.md)
- [orchestrator/README.md](orchestrator/README.md)
- [orchestrator/docs/README.md](orchestrator/docs/README.md)

## Тесты

Примеры запуска:

```bash
cd game && python -m pytest -q
cd poller && python -m pytest -q
cd orchestrator && python -m pytest -q
```

## Автор

- ФИО: Югай Александр Леонидович
- Telegram: @lep3ha
- Email: alexandr.youguy@gmail.com

