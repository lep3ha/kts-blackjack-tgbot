## Слайд 1 — Проект в 30 секунд

- Telegram-бот для Blackjack (single и group режимы)
- Команды: `/single_start`, `/create_lobby`, `/join`, `/group_start`, `/stop`
- Таймер хода: при timeout автоматически выполняется Stand
- Админ-функции: top-up и ban
- Архитектура: event-driven микросервисы

---

## Слайд 2 — Общая схема

```text
Telegram API -> Poller -> Kafka (telegram.updates.raw) -> Orchestrator -> Game Service
```

- Poller забирает апдейты из Telegram
- Orchestrator нормализует команды и вызывает игровой API
- Game Service хранит сессии и считает логику раунда
- Redis: dedup, контекст сессий, таймеры
- PostgreSQL: персистентные игровые данные

---

## Слайд 3 — Poller: что делает

- Long polling Telegram API
- Публикация апдейтов в Kafka
- Хранение offset в файле (`poller_state` volume)
- Retry/backoff и аккуратный shutdown

**Стек:** `aiohttp`, `aiokafka`, `pydantic`

---

## Слайд 4 — Orchestrator: центр управления

- Читает события из Kafka
- Преобразует update -> команда
- Вызывает Game Service (HTTP)
- Отправляет ответ в Telegram с кнопками Hit/Stand/Double
- Управляет таймерами хода

**Стек:** `aiohttp`, `aiokafka`, `redis`, `pydantic`

---

## Слайд 5 — Orchestrator: надежность

- Дедупликация апдейтов по `update_id`
- Отмена таймера после успешного действия текущего игрока
- Подавление ложных timeout-уведомлений
- Локальная проверка: не твой ход / недоступное действие
- Fail-safe обработка transport ошибок

Результат: устойчивый UX без лишних сообщений и гонок таймера.

---

## Слайд 6 — Game Service: архитектура

- HTTP API для игровых операций
- State machine для хода раунда
- Domain-правила отделены от persistence
- Транзакционная запись всех side effects

**Стек:** `aiohttp`, `SQLAlchemy`, `asyncpg`, `alembic`, `python-statemachine`

---

## Слайд 7 — State Machine (игра)

`waiting -> dealing -> player_turn -> dealer_turn -> resolving -> closed`

- Поддерживаемые действия: `hit`, `stand`, `double`
- Timeout трактуется как forced `stand`
- После действия работает auto-drain terminal фаз
- Persisted lifecycle: `lobby_open -> in_progress -> stopped -> closed`

---

## Слайд 8 — Данные и инфраструктура

**Ключевые сущности БД:**
- `Player`, `Deck`, `GameSession`, `PlayerToSession`, `State`

**Compose-окружение:**
- `db` (PostgreSQL 15), `redis`, `redpanda`
- `poller`, `orchestrator`, `game`
- Volumes: `db_data`, `poller_state`

---

## Слайд 9 — Тесты и выводы

- Unit + integration тесты по всем сервисам
- В orchestrator покрыты pipeline/handlers/timers (118+ тестов)
- Проверены race-сценарии и timeout-поток

**Главные принципы:**
- Event-driven decoupling
- Idempotency + dedup
- Domain isolation
- Fail-safe обработка ошибок

---
## Слайд 10 — Демо для комиссии (QR)

Отсканируйте QR-код и попробуйте бота в Telegram.

**После сканирования:**
1. Нажмите Start
2. Выполните `/single_start 100`
3. Сыграйте раунд через кнопки Hit / Stand / Double

![QR-код для запуска бота](./presentation/assets/qr-bot.png)

Если QR-код не работает, найдите бота по имени `@blackjack_by_lep3ha_bot` в Telegram и начните с ним диалог.
