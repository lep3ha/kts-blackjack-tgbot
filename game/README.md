# Game Service

`game` — HTTP JSON API с доменной логикой blackjack, PostgreSQL persistence и Alembic-мigrations.

## Ответственность сервиса

Сервис отвечает за:
- хранение игроков, колод, сессий и аудита переходов;
- валидацию игровых действий и timeout-событий;
- расчет дилера, settlement и обновление балансов;
- bot-facing HTTP API для `orchestrator`.

Сервис не отвечает за:
- работу с Telegram Bot API;
- Kafka и Redis transport-логику;
- dedup и управление чатовым UX.

## Быстрый старт

Полный стек лучше запускать из корня проекта:

```bash
docker compose up --build
```

Для отдельного локального запуска `game`:

```bash
python -m pip install -r requirements.txt
python -m alembic upgrade head
python run.py
```

По умолчанию сервис стартует на `http://0.0.0.0:8001`.

## Конфигурация

Основные переменные окружения:
- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `HOST`
- `PORT`
- `DEBUG`
- `BOT_SNAPSHOT_INCLUDE_LEGACY_FIELDS`

Значения по умолчанию:
- Postgres host: `localhost`
- Postgres port: `5433`
- DB name: `game_service`
- user/password: `postgres` / `postgres`
- HTTP host/port: `0.0.0.0:8001`

## Основные ручки

### Служебные

- `GET /health`
- `GET /openapi.json`

### Каталог

- `POST /players`
- `POST /decks`
- `POST /sessions`
- `PUT /sessions/{session_id}/players`

### Runtime API

- `PUT /sessions/{session_id}/start`
- `PUT /sessions/{session_id}/actions`
- `PUT /sessions/{session_id}/timeout`
- `GET /sessions/{session_id}`

### Bot-facing API

- `POST /bot/sessions/group/open`
- `POST /bot/sessions/group/join`
- `GET /bot/sessions/group/lobby`
- `POST /bot/sessions/group/start`
- `POST /bot/sessions/group/player-stop`
- `POST /bot/sessions/single/start`
- `POST /bot/sessions/single/stop`
- `GET /bot/sessions/current`
- `GET /bot/sessions/last`
- `POST /bot/sessions/action`
- `POST /bot/sessions/timeout`
- `POST /admin/topup`
- `POST /admin/ban`

## Важные игровые семантики

- `single_stop` не делает мгновенный расчет по текущим картам; он эквивалентен действию `stand` для активного игрока, после чего раунд доигрывается обычным путем.
- `group player stop` выводит игрока из активного группового раунда, сохраняя оставшуюся сессию, если в ней еще есть активные участники.
- при `split` после завершения первой руки ход должен перейти на вторую руку того же игрока; переход к дилеру возможен только после завершения всех активных рук игроков.
- timeout текущего игрока трактуется как forced `stand`, но только если таймер действительно истек.
- после пользовательского действия сервис автоматически дренирует terminal phases: ход дилера и settlement.

## Тесты

```bash
python -m pytest -q
```

Интеграционные тесты используют PostgreSQL. Для полного локального прогона удобнее запускать их в docker-compose окружении.

## Документация

- [docs/README.md](docs/README.md)
- [docs/service_overview.md](docs/service_overview.md)
- [docs/api.md](docs/api.md)
- [docs/game_logic.md](docs/game_logic.md)
- [docs/state_machine.md](docs/state_machine.md)
- [docs/entities.md](docs/entities.md)
- [docs/blackjack_architecture.md](docs/blackjack_architecture.md)

## Автор

- ФИО: Югай Александр Леонидович
- Telegram: @lep3ha
- Email: alexandr.youguy@gmail.com
