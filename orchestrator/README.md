# Orchestrator Service

`orchestrator` связывает транспортный слой Telegram/Kafka с игровым HTTP API и Telegram-ответами.

## Ответственность сервиса

Сервис делает:
- чтение `TelegramUpdateEnvelope` из Kafka;
- нормализацию сообщений, reply-кнопок и callback-query в команды;
- вызовы `game` HTTP API;
- рендеринг текста, клавиатур и отправку ответов в Telegram;
- хранение dedup, session context и timer tasks в Redis.

## Быстрый старт

Полный стек:

```bash
docker compose up --build
```

Локально только `orchestrator`:

```bash
python -m pip install -r requirements.txt
python run.py
```

## Основные настройки

- `APP_NAME`
- `LOG_LEVEL`
- `GAME_SERVICE_BASE_URL`
- `GAME_SERVICE_REQUEST_TIMEOUT_SECONDS`
- `REDIS_URL`
- `DEDUP_TTL_SECONDS`
- `SESSION_CONTEXT_TTL_SECONDS`
- `TIMER_RETENTION_SECONDS`
- `TIMER_POLL_INTERVAL_SECONDS`
- `TIMER_CLAIM_TTL_SECONDS`
- `TELEGRAM_BASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `SENDER_REQUEST_TIMEOUT_SECONDS`
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_TOPIC_UPDATES`
- `KAFKA_GROUP_ID`
- `KAFKA_AUTO_OFFSET_RESET`

## Важные runtime семантики

- reply text `Присоединиться (N)` нормализуется в `group_join` с извлечением ставки;
- callback `session:join:<bet>` нормализуется в `group_join`, callback `session:start:group` — в `group_start`;
- post-game UX теперь inline-only: `session:create:group` -> `group_open`, `session:create:single` -> `single_start`;
- `single_stop` на уровне bot UX идет в game как auto-stand текущего игрока;
- split-контекст передается через `turn_version` и `hand_index`: callback payload вида `action:<move>:tv:<turn_version>:hand:<hand_index>`, а message/reply действия при отсутствии `tv`/`hand` наследуют значения из `SessionContext`;
- страховка поддерживается как `player_action`: `/insurance`, `Insurance`, callback `action:insurance:tv:<turn_version>[:hand:<hand_index>]`;
- local guards режут stale turn, ход не того игрока и недоступные действия до вызова game API;
- таймеры ходов планируются через Redis worker и не должны отправлять ложные timeout-уведомления;
- cleanup старого игрового сообщения выполняется только для успешного хода текущего игрока.

## Тесты

```bash
python -m pytest -q
```

## Документация

- [docs/README.md](docs/README.md)
- [docs/service_overview.md](docs/service_overview.md)
- [docs/entities.md](docs/entities.md)
- [docs/command_flow.md](docs/command_flow.md)

## Автор

- ФИО: Югай Александр Леонидович
- Telegram: @lep3ha
- Email: alexandr.youguy@gmail.com
