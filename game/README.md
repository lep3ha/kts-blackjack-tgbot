## Game Service (Blackjack)

Мини-сервис с HTTP JSON API для blackjack.

> **Полный стек** (с poller, router, Kafka, Redis) поднимается из корня проекта:
> ```bash
> docker compose up --build   # из папки kts-blackjack-tgbot/
> ```
> `game/docker-compose.yml` предназначен для изолированной разработки и тестирования game-сервиса без остальных компонентов.

### Быстрый старт (Postgres + миграции)

Поднять Postgres + game-service в Docker (Postgres наружу `5433`, API наружу `8001`):

```bash
docker compose up -d --build
```

Миграции применяются автоматически при старте `game`-сервиса (через `alembic upgrade head`).

Если хочешь поднять только Postgres (без сервиса):

```bash
docker compose up -d db
```

Установить зависимости:

```bash
python -m pip install -r requirements.txt
```

Применить миграции Alembic:

```bash
python -m alembic upgrade head
```

Дефолтные параметры БД (см. `app/core/config.py`):
- host: `localhost`
- port: `5433`
- db: `game_service`
- user/password: `postgres` / `postgres`

Можно переопределять через переменные окружения или `.env` (регистр не важен):
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`

### Запуск сервиса

```bash
python run.py
```

По умолчанию сервис стартует на `http://0.0.0.0:8001`.

Полезные ручки:
- `GET /health`
- `GET /openapi.json`

### Тесты

Юнит/HTTP-тесты:

```bash
python -m pytest -q
```

Интеграционные тесты используют Postgres и могут скипаться, если БД недоступна.

## Автор

- ФИО: Югай Александр Леонидович
- Telegram: @lep3ha
- Email: alexandr.youguy@gmail.com
