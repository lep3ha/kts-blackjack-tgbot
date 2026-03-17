# Контракт API

Сервис предоставляет HTTP JSON API (`application/json`). Все ответы обёрнуты в единый конверт.

## Содержание

- [Формат ответов](#формат-ответов)
- [Коды ошибок](#коды-ошибок)
- [Служебные ручки](#служебные-ручки)
- [Каталог (`/players`, `/decks`, `/sessions`)](#эндпоинты-каталога)
- [Runtime Blackjack (`/sessions/{id}/…`)](#эндпоинты-runtime-blackjack)
- [Bot API (`/bot/sessions/…`)](#bot-api)
- [Снимки сессии](#снимки-сессии)
- [Справочник статусов и значений](#справочник-статусов-и-значений)

---

## Формат ответов

### Успех

```json
{
  "success": true,
  "data": { "...": "..." }
}
```

### Ошибка

```json
{
  "success": false,
  "error": {
    "code": "bad_request",
    "message": "описание для диагностики",
    "details": {}
  }
}
```

> `details` — опциональное поле, присутствует только у `validation_error`.  
> `message` — нестабильная строка для логов. Не парсить в клиентском коде.

---

## Коды ошибок

| `error.code`        | HTTP | Когда возникает                                                                 |
|---------------------|------|---------------------------------------------------------------------------------|
| `bad_request`       | 400  | Невалидный формат поля, неверный `chat_type` для эндпоинта                     |
| `bad_json`          | 400  | Тело запроса не является корректным JSON                                        |
| `validation_error`  | 400  | Pydantic-ошибка при разборе модели (редко)                                      |
| `authorization_error` | 403 | Действие запрещено доменными правилами (например, не-администратор открывает lobby) |
| `not_found`         | 404  | Ресурс не найден (игрок, сессия, lobby)                                        |
| `state_conflict`    | 409  | Конфликт состояния: lobby не открыто, сессия уже есть, игрок не активен и т.д. |
| `stale_turn`        | 409  | `turn_version` не совпадает с текущим ходом                                    |
| `game_logic_error`  | 422  | Нарушение правил игры: недостаточный банк, недоступное действие                 |
| `internal_error`    | 500  | Непредвиденная ошибка сервера                                                   |

---

## Служебные ручки

### `GET /health`

Проверка доступности сервиса.

**Ответ 200:**
```json
{ "success": true, "data": { "status": "ok" } }
```

### `GET /openapi.json`

Минимальная OpenAPI 3.0 спецификация, сгенерированная из swagger-деораторов к каждой ручке.

---

## Эндпоинты каталога

### `POST /players`

Создаёт запись игрока.

**Тело запроса:**
```json
{
  "telegram_id": "123456789",
  "bank": 1000
}
```

| Поле          | Тип    | Ограничения | Описание            |
|---------------|--------|-------------|---------------------|
| `telegram_id` | string | 1..64 символа | Telegram user ID  |
| `bank`        | int    | >= 0        | Начальный баланс    |

**Ответ 201:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "telegram_id": "123456789",
    "bank": 1000
  }
}
```

**Ошибки:**
- `400 bad_request` — невалидный `telegram_id` или `bank`

---

### `POST /decks`

Создаёт логический контекст чата (deck).

**Тело запроса:**
```json
{
  "chat_id": "-100123456789",
  "meta": {}
}
```

| Поле      | Тип    | Ограничения  | Описание                              |
|-----------|--------|--------------|---------------------------------------|
| `chat_id` | string | 1..64 символа | Telegram chat ID (группа или личка)  |
| `meta`    | object | —            | Произвольные метаданные, по умолчанию `{}` |

**Ответ 201:**
```json
{
  "success": true,
  "data": {
    "id": 5,
    "chat_id": "-100123456789",
    "meta": {}
  }
}
```

---

### `POST /sessions`

Создаёт blackjack-сессию, привязанную к deck. Начальный статус — `lobby_open`.

**Тело запроса:**
```json
{
  "deck_id": 5,
  "count_players": 4
}
```

| Поле            | Тип | Ограничения   | Описание                             |
|-----------------|-----|---------------|--------------------------------------|
| `deck_id`       | int | > 0           | ID deck                              |
| `count_players` | int | 1..8, default 8 | Максимальное число игровых мест    |

**Ответ 201:**
```json
{
  "success": true,
  "data": {
    "id": 42,
    "deck_id": 5,
    "status": "lobby_open",
    "count_players": 4
  }
}
```

**Ошибки:**
- `404 not_found` — deck не найден

---

### `PUT /sessions/{session_id}/players`

Сажает игрока за стол в указанную позицию.

**Path params:**
- `session_id: int` — ID сессии

**Тело запроса:**
```json
{
  "player_id": 1,
  "position": 2,
  "bet": 100
}
```

| Поле        | Тип | Ограничения | Описание               |
|-------------|-----|-------------|------------------------|
| `player_id` | int | > 0         | ID игрока              |
| `position`  | int | 1..8        | Позиция за столом      |
| `bet`       | int | > 0         | Ставка                 |

**Ответ 201:**
```json
{
  "success": true,
  "data": {
    "session_id": 42,
    "player_id": 1,
    "position": 2,
    "bet": 100
  }
}
```

**Ошибки:**
- `404 not_found` — сессия или игрок не найдены
- `409 state_conflict` — позиция занята, ставка не соответствует ограничениям, сессия не в статусе `lobby_open`

---

## Эндпоинты Runtime Blackjack

Ручной режим управления сессией по `session_id`. Используется для отладки и интеграционного тестирования. В продакшн-потоке сессией управляет Bot API.

Все ответы — `SessionStateResponse` (см. [Снимки сессии](#снимки-сессии)).

---

### `PUT /sessions/{session_id}/start`

Раздаёт стартовые карты всем игрокам и дилеру, переводит сессию в `in_progress`, активирует первый ход.

**Path params:**
- `session_id: int`

**Тело запроса:** отсутствует.

**Ответ 200:** `SessionStateResponse`

**Ошибки:**
- `404 not_found` — сессия не найдена
- `409 state_conflict` — сессия не в состоянии `waiting` (уже начата или завершена)

---

### `PUT /sessions/{session_id}/actions`

Применяет действие активного игрока.

**Path params:**
- `session_id: int`

**Тело запроса:**
```json
{
  "position": 2,
  "action": "hit"
}
```

| Поле       | Тип    | Допустимые значения       | Описание             |
|------------|--------|---------------------------|----------------------|
| `position` | int    | 1..8                      | Позиция игрока       |
| `action`   | string | `hit`, `stand`, `double`  | Действие             |

**Ответ 200:** `SessionStateResponse`

**Ошибки:**
- `404 not_found` — сессия не найдена
- `409 state_conflict` — не ход игрока на данной позиции
- `422 game_logic_error` — действие недоступно (например, `double` при нехватке банка)

---

### `PUT /sessions/{session_id}/timeout`

Форсирует обработку таймаута текущего хода. Если `position` не передана — применяется к текущей активной позиции.

**Path params:**
- `session_id: int`

**Тело запроса:**
```json
{
  "position": 2
}
```

| Поле       | Тип       | Описание                                                |
|------------|-----------|---------------------------------------------------------|
| `position` | int\|null | Позиция (1..8), опционально. `null` — текущая позиция  |

**Ответ 200:** `SessionStateResponse`

**Ошибки:**
- `404 not_found` — сессия не найдена
- `409 state_conflict` — позиция не активна

---

### `GET /sessions/{session_id}`

Возвращает текущий снимок состояния сессии.

**Path params:**
- `session_id: int`

**Ответ 200:** `SessionStateResponse`

**Ошибки:**
- `404 not_found` — сессия не найдена

---

## Bot API

Высокоуровневый API для управления сессиями через Telegram-бота. Все ручки работают через `chat_id` + `actor_telegram_id`, без явного `session_id`. Возвращают [bot snapshot](#снимки-сессии).

### Групповой игровой процесс

```
POST /bot/sessions/group/open    ← администратор открывает lobby
POST /bot/sessions/group/join    ← другие игроки подключаются
GET  /bot/sessions/group/lobby   ← состояние lobby
POST /bot/sessions/group/start   ← администратор стартует игру
POST /bot/sessions/action        ← каждый игрок делает ход (hit/stand/double)
POST /bot/sessions/group/player-stop  ← игрок останавливается (stand)
POST /bot/sessions/timeout       ← таймер истёк
```

### Одиночный игровой процесс

```
POST /bot/sessions/single/start  ← игрок начинает одиночную партию
POST /bot/sessions/action        ← делает ход
POST /bot/sessions/single/stop   ← останавливает сессию
```

---

### `POST /bot/sessions/group/open`

Открывает group lobby и автоматически записывает актёра как первого участника.

**Требования:** актёр должен быть администратором (`actor_is_admin: true`). Если lobby для этого `chat_id` уже открыто — `409 state_conflict`.

**Тело запроса:**
```json
{
  "chat_id": "-100123456789",
  "chat_type": "group",
  "actor_telegram_id": "111222333",
  "actor_is_admin": true,
  "bet": 100,
  "count_players": 4
}
```

| Поле                 | Тип    | Ограничения  | Описание                          |
|----------------------|--------|--------------|-----------------------------------|
| `chat_id`            | string | 1..64        | Telegram chat ID                  |
| `chat_type`          | string | `"group"`    | Фиксированное значение            |
| `actor_telegram_id`  | string | 1..64        | Telegram ID инициатора            |
| `actor_is_admin`     | bool   | —            | Должен быть `true`                |
| `bet`                | int    | > 0          | Ставка актёра                     |
| `count_players`      | int    | 1..8, default 8 | Максимум мест               |

**Ответ 201:** bot snapshot (`GroupSessionSnapshotResponse`)

**Ошибки:**
- `403 authorization_error` — `actor_is_admin: false`
- `404 not_found` — игрок с `actor_telegram_id` не зарегистрирован
- `409 state_conflict` — lobby уже открыто
- `422 game_logic_error` — недостаточный банк для ставки

---

### `POST /bot/sessions/group/join`

Присоединяет участника к текущему group lobby.

**Тело запроса:**
```json
{
  "chat_id": "-100123456789",
  "chat_type": "group",
  "actor_telegram_id": "444555666",
  "bet": 100
}
```

| Поле                | Тип    | Ограничения | Описание               |
|---------------------|--------|-------------|------------------------|
| `chat_id`           | string | 1..64       | Telegram chat ID       |
| `chat_type`         | string | `"group"`   | Фиксированное значение |
| `actor_telegram_id` | string | 1..64       | Telegram ID вступающего |
| `bet`               | int    | > 0         | Ставка                 |

**Ответ 200:** bot snapshot

**Ошибки:**
- `404 not_found` — lobby не найдено, игрок не зарегистрирован
- `409 state_conflict` — игрок уже в lobby, lobby заполнено
- `422 game_logic_error` — недостаточный банк

---

### `GET /bot/sessions/group/lobby`

Возвращает текущее состояние group lobby (может быть вызвано до старта).

**Query params:**

| Параметр  | Тип    | Ограничения | Описание         |
|-----------|--------|-------------|------------------|
| `chat_id` | string | 1..64       | Telegram chat ID |

**Ответ 200:** bot snapshot

**Ошибки:**
- `404 not_found` — активное lobby не найдено

---

### `POST /bot/sessions/group/start`

Стартует групповую игру: раздаёт карты, активирует первый ход.

**Требования:** актёр — администратор; lobby должно быть в состоянии `can_start: true` (минимум один участник).

**Тело запроса:**
```json
{
  "chat_id": "-100123456789",
  "chat_type": "group",
  "actor_telegram_id": "111222333",
  "actor_is_admin": true
}
```

| Поле                | Тип    | Ограничения | Описание               |
|---------------------|--------|-------------|------------------------|
| `chat_id`           | string | 1..64       | Telegram chat ID       |
| `chat_type`         | string | `"group"`   | Фиксированное значение |
| `actor_telegram_id` | string | 1..64       | Telegram ID              |
| `actor_is_admin`    | bool   | —           | Должен быть `true`     |

**Ответ 200:** bot snapshot

**Ошибки:**
- `403 authorization_error` — `actor_is_admin: false`
- `404 not_found` — lobby не найдено
- `409 state_conflict` — lobby нельзя стартовать (`can_start: false`)

---

### `POST /bot/sessions/group/player-stop`

Останавливает текущего участника group-игры (эквивалент `stand` для активного игрока).

**Тело запроса:**
```json
{
  "chat_id": "-100123456789",
  "chat_type": "group",
  "actor_telegram_id": "444555666"
}
```

| Поле                | Тип    | Ограничения | Описание               |
|---------------------|--------|-------------|------------------------|
| `chat_id`           | string | 1..64       | Telegram chat ID       |
| `chat_type`         | string | `"group"`   | Фиксированное значение |
| `actor_telegram_id` | string | 1..64       | Telegram ID            |

**Ответ 200:** bot snapshot

**Ошибки:**
- `404 not_found` — сессия или игрок не найдены
- `409 state_conflict` — не ход этого игрока

---

### `POST /bot/sessions/single/start`

Создаёт и сразу стартует одиночную сессию для `actor_telegram_id`.

**Тело запроса:**
```json
{
  "chat_id": "111222333",
  "chat_type": "single",
  "actor_telegram_id": "111222333",
  "bet": 50
}
```

| Поле                | Тип    | Ограничения   | Описание               |
|---------------------|--------|---------------|------------------------|
| `chat_id`           | string | 1..64         | Telegram chat ID (личка) |
| `chat_type`         | string | `"single"`    | Фиксированное значение |
| `actor_telegram_id` | string | 1..64         | Telegram ID            |
| `bet`               | int    | > 0           | Ставка                 |

**Ответ 200:** bot snapshot

**Ошибки:**
- `404 not_found` — игрок не зарегистрирован
- `409 state_conflict` — у игрока уже есть активная одиночная сессия
- `422 game_logic_error` — недостаточный банк

---

### `POST /bot/sessions/single/stop`

Останавливает активную одиночную сессию и закрывает её.

**Тело запроса:**
```json
{
  "chat_id": "111222333",
  "chat_type": "single",
  "actor_telegram_id": "111222333"
}
```

**Ответ 200:** bot snapshot (финальный, со статусом `closed`)

**Ошибки:**
- `404 not_found` — активная сессия не найдена

---

### `GET /bot/sessions/current`

Возвращает текущую незавершённую bot-сессию для данного чата.

**Query params:**

| Параметр    | Тип    | Допустимые значения  | Описание         |
|-------------|--------|----------------------|------------------|
| `chat_id`   | string | 1..64                | Telegram chat ID |
| `chat_type` | string | `"group"`, `"single"` | Тип чата        |

**Ответ 200:** bot snapshot

**Ошибки:**
- `404 not_found` — нет активной сессии

---

### `GET /bot/sessions/last`

Возвращает последнюю завершённую (закрытую) bot-сессию для данного чата.

**Query params:**

| Параметр    | Тип    | Допустимые значения  | Описание         |
|-------------|--------|----------------------|------------------|
| `chat_id`   | string | 1..64                | Telegram chat ID |
| `chat_type` | string | `"group"`, `"single"` | Тип чата        |

**Ответ 200:** bot snapshot

**Ошибки:**
- `404 not_found` — нет завершённых сессий

---

### `POST /bot/sessions/action`

Применяет действие игрока в активной bot-сессии. Защищён от гонок через `turn_version`.

**Тело запроса:**
```json
{
  "chat_id": "-100123456789",
  "chat_type": "group",
  "actor_telegram_id": "444555666",
  "action": "hit",
  "turn_version": 3
}
```

| Поле                | Тип    | Ограничения                    | Описание                                        |
|---------------------|--------|--------------------------------|-------------------------------------------------|
| `chat_id`           | string | 1..64                          | Telegram chat ID                                |
| `chat_type`         | string | `"group"`, `"single"`          | Тип чата                                        |
| `actor_telegram_id` | string | 1..64                          | Telegram ID действующего игрока                 |
| `action`            | string | `hit`, `stand`, `double`       | Действие                                        |
| `turn_version`      | int    | >= 0                           | Версия хода из актуального snapshot             |

**Ответ 200:** bot snapshot

**Ошибки:**
- `404 not_found` — сессия не найдена
- `409 stale_turn` — `turn_version` не совпадает с текущим ходом (запрос устарел)
- `409 state_conflict` — не ход этого игрока
- `422 game_logic_error` — действие недоступно

---

### `POST /bot/sessions/timeout`

Применяет таймаут к текущему ходу в bot-сессии. Вызывается таймерным воркером Router-сервиса.

**Тело запроса:**
```json
{
  "chat_id": "-100123456789",
  "chat_type": "group",
  "turn_version": 3
}
```

| Поле           | Тип    | Ограничения           | Описание                            |
|----------------|--------|-----------------------|-------------------------------------|
| `chat_id`      | string | 1..64                 | Telegram chat ID                    |
| `chat_type`    | string | `"group"`, `"single"` | Тип чата                            |
| `turn_version` | int    | >= 0                  | Версия хода из актуального snapshot |

**Ответ 200:** bot snapshot

**Ошибки:**
- `404 not_found` — сессия не найдена
- `409 stale_turn` — `turn_version` устарел (таймер прибыл слишком поздно)

---

## Снимки сессии

### `SessionStateResponse` (runtime-режим)

Возвращается ручками `/sessions/{session_id}/…`.

```json
{
  "session_id": 42,
  "deck_id": 5,
  "status": "in_progress",
  "state": "player_turn",
  "available_moves": ["hit", "stand", "double"],
  "current_position": 2,
  "current_timer": "2024-01-15T10:30:00+00:00",
  "dealer_cards": ["Ah", "5d"],
  "players": [
    {
      "player_id": 1,
      "position": 2,
      "bet": 100,
      "cards": ["Kh", "9s"],
      "bank": 900
    }
  ]
}
```

| Поле               | Тип          | Описание                                           |
|--------------------|--------------|---------------------------------------------------|
| `session_id`       | int          | ID сессии                                         |
| `deck_id`          | int          | ID deck                                           |
| `status`           | string       | [Статус сессии](#session_status)                  |
| `state`            | string       | [Runtime state](#runtime_state)                   |
| `available_moves`  | string[]     | Доступные действия для текущей позиции            |
| `current_position` | int\|null    | Номер активной позиции                            |
| `current_timer`    | string\|null | ISO 8601 — дедлайн хода (может быть `null`)       |
| `dealer_cards`     | string[]     | Карты дилера (краткая нотация: `Ah`, `Td`, `2s`)  |
| `players`          | object[]     | Список `PlayerStateResponse`                      |

**`PlayerStateResponse`:**

| Поле        | Тип      | Описание          |
|-------------|----------|-------------------|
| `player_id` | int      | ID игрока         |
| `position`  | int      | Позиция (1..8)    |
| `bet`       | int      | Ставка            |
| `cards`     | string[] | Карты игрока      |
| `bank`      | int      | Текущий банк      |

---

### Bot Snapshot (`GroupSessionSnapshotResponse`)

Возвращается всеми ручками `/bot/sessions/…`. Формат зависит от настройки `BOT_SNAPSHOT_INCLUDE_LEGACY_FIELDS` (env var, default `true`).

```json
{
  "chat_id": "-100123456789",
  "chat_mode": "group",
  "session_id": 42,
  "session_status": "in_progress",
  "runtime_state": "player_turn",
  "turn_version": 3,
  "current_player": {
    "telegram_id": "444555666",
    "position": 2
  },
  "dealer": {
    "cards": ["Ah", "?"],
    "is_final": false
  },
  "lobby": {
    "count_players": 4,
    "participants_count": 2,
    "can_start": true,
    "start_error": null
  },
  "summary": {
    "participants_count": 2,
    "results_count": 0,
    "total_delta": 0
  },
  "available_moves": ["hit", "stand", "double"],
  "current_timer": "2024-01-15T10:30:00+00:00",
  "participants": [
    {
      "telegram_id": "444555666",
      "player_id": 1,
      "position": 2,
      "participant_status": "active",
      "bet": 100,
      "cards": ["Kh", "9s"],
      "bank": 900,
      "result": null,
      "delta": null
    }
  ],
  "current_position": 2,
  "dealer_cards": ["Ah", "?"],
  "can_start": true,
  "start_error": null
}
```

**Основные поля:**

| Поле             | Тип          | Описание                                          |
|------------------|--------------|---------------------------------------------------|
| `chat_id`        | string       | Telegram chat ID                                  |
| `chat_mode`      | string       | `"group"` или `"single"`                          |
| `session_id`     | int\|null    | ID сессии (`null` если сессии нет)               |
| `session_status` | string\|null | [Статус сессии](#session_status)                  |
| `runtime_state`  | string\|null | [Runtime state](#runtime_state)                   |
| `turn_version`   | int\|null    | Монотонно возрастающая версия хода               |
| `current_player` | object\|null | `CurrentPlayerResponse` (ниже)                   |
| `dealer`         | object\|null | `DealerSnapshotResponse` (ниже)                  |
| `lobby`          | object\|null | `LobbySnapshotResponse` (ниже)                   |
| `summary`        | object\|null | `SummarySnapshotResponse` (ниже)                 |
| `available_moves`| string[]     | Допустимые действия (пуст вне хода)              |
| `current_timer`  | string\|null | ISO 8601 — дедлайн хода                          |
| `participants`   | object[]     | `GroupParticipantResponse[]`                     |

**Legacy-поля** (присутствуют только при `BOT_SNAPSHOT_INCLUDE_LEGACY_FIELDS=true`):

| Поле               | Тип          | Описание (дублирует canonical-структуры)     |
|--------------------|--------------|----------------------------------------------|
| `current_position` | int\|null    | Дубль `current_player.position`              |
| `dealer_cards`     | string[]     | Дубль `dealer.cards`                         |
| `can_start`        | bool\|null   | Дубль `lobby.can_start`                      |
| `start_error`      | string\|null | Дубль `lobby.start_error`                    |

Для новых интеграций используйте canonical-поля. Legacy-поля будут удалены в будущих версиях.

---

**`CurrentPlayerResponse`:**

| Поле          | Тип    | Описание                                |
|---------------|--------|-----------------------------------------|
| `telegram_id` | string | Telegram ID текущего игрока             |
| `position`    | int    | Позиция (1..8)                          |

---

**`DealerSnapshotResponse`:**

| Поле       | Тип      | Описание                                                  |
|------------|----------|-----------------------------------------------------------|
| `cards`    | string[] | Карты дилера. Скрытая карта обозначается `"?"` до вскрытия |
| `is_final` | bool     | `true` — дилер сделал все ходы, карты открыты            |

---

**`LobbySnapshotResponse`:**

| Поле                 | Тип          | Описание                                                    |
|----------------------|--------------|-------------------------------------------------------------|
| `count_players`      | int          | Максимальное число мест                                     |
| `participants_count` | int          | Число записавшихся участников                               |
| `can_start`          | bool         | `true` — можно стартовать игру                             |
| `start_error`        | string\|null | Строковая причина почему нельзя стартовать (`null` если можно) |

---

**`SummarySnapshotResponse`:**

| Поле                 | Тип | Описание                               |
|----------------------|-----|----------------------------------------|
| `participants_count` | int | Число участников итого                 |
| `results_count`      | int | Число участников с финальным результатом |
| `total_delta`        | int | Суммарное изменение банков              |

---

**`GroupParticipantResponse`:**

| Поле                 | Тип          | Описание                                            |
|----------------------|--------------|-----------------------------------------------------|
| `telegram_id`        | string       | Telegram ID участника                               |
| `player_id`          | int          | ID игрока в БД                                      |
| `position`           | int          | Позиция (1..8)                                      |
| `participant_status` | string       | [Статус участника](#participant_status)             |
| `bet`                | int          | Ставка                                              |
| `cards`              | string[]     | Карты (видны всем после старта)                     |
| `bank`               | int          | Текущий банк                                        |
| `result`             | string\|null | [Результат](#result) (`null` пока не рассчитан)    |
| `delta`              | int\|null    | Изменение банка (`null` пока не рассчитан)          |

---

## Справочник статусов и значений

### `session_status`

| Значение      | Описание                                                              |
|---------------|-----------------------------------------------------------------------|
| `lobby_open`  | Сессия создана, идёт набор игроков                                    |
| `in_progress` | Игра идёт (карты розданы, ходы делаются)                             |
| `stopped`     | Игра остановлена (принудительно или по таймауту), ожидает закрытия   |
| `closed`      | Сессия завершена, результаты зафиксированы                           |

### `runtime_state`

| Значение      | Описание                                           |
|---------------|----------------------------------------------------|
| `waiting`     | Ожидание старта (перед раздачей карт)             |
| `dealing`     | Раздача карт                                       |
| `player_turn` | Ход игрока — кто-то должен сделать действие        |
| `dealer_turn` | Ход дилера — автоматические действия дилера       |
| `resolving`   | Подсчёт результатов                               |
| `closed`      | Сессия завершена                                   |

### `participant_status`

| Значение   | Описание                                                             |
|------------|----------------------------------------------------------------------|
| `joined`   | Записался в lobby, игра ещё не началась                             |
| `active`   | Участвует в игре, ещё не завершил ход                               |
| `inactive` | Завершил свой ход (stand, double, bust) но игра ещё не закрыта     |
| `settled`  | Результат зафиксирован, банк обновлён                               |

### `result`

| Значение    | Описание                                               |
|-------------|--------------------------------------------------------|
| `win`       | Победа (набрал больше дилера, не превысив 21)         |
| `lose`      | Проигрыш                                               |
| `push`      | Ничья (одинаковое количество очков с дилером)         |
| `blackjack` | Блэкджек (21 с двух первых карт)                      |
| `bust`      | Перебор (сумма карт > 21)                             |
| `stopped`   | Игра была остановлена, результат не определён         |
