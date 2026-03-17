# Router Command Processing Flow

## End-to-end pipeline

1. `KafkaUpdatesConsumer` получает envelope.
2. `RouterPipeline.process_envelope()` загружает session context.
3. `TelegramUpdateNormalizer` превращает payload в `RouterCommand`.
4. `DeduplicatingCommandProcessor` проверяет dedup key.
5. `RouterCommandDispatcher` выбирает handler по `command_type`.
6. `GameCommandHandlers` вызывает `game` API или возвращает локальный result.
7. `present_router_result()` формирует текст и клавиатуру.
8. `TelegramSenderClient` отправляет ответ в Telegram.
9. `RouterPipeline` обновляет `SessionContext` и scheduling hints.

## Нормализация команд

Источники команд:
- текстовые slash-команды (`/start`, `/single_start`, `/create_lobby`, `/group_start`, ...)
- reply keyboard (`Начать игру`, `Текущая`, `Остановить игру`, ...)
- callback data inline-кнопок (`action:hit`, ...)

Ключевая семантика slash-команд:
- `/create_lobby <bet>` -> открывает новое групповое лобби
- `/group_start` -> запускает уже открытое лобби
- `/join <bet>` -> присоединяет игрока к открытому лобби
- `/stop` -> в `single` завершает сессию, в `group` переводит игрока в inactive через group player stop
- `/start_round` -> legacy alias для `/group_start`

Для групп поддерживается Telegram-вариант slash-команд с mention бота:
- `/start@blackjack_by_lep3ha_bot`
- `/create_lobby@blackjack_by_lep3ha_bot 200`
- `/group_start@blackjack_by_lep3ha_bot`

Специальный кейс:
- `Начать игру` маршрутизируется контекстно через `reply_action_hint`. До открытия лобби это ведёт в `group_open`, после открытия лобби — в `group_start`. 

## Ошибки и отказоустойчивость

- неподдерживаемый input -> `command_type=unsupported`
- дубликаты update не переобрабатываются
- сетевые ошибки game/telegram маппятся в понятные user-facing сообщения

## Таймеры

`RedisTimerWorker` отвечает за timeout-задачи:
- планирование при старте/смене хода
- claim и выполнение задач
- вызов timeout executor, связанного с game service
