# Orchestrator Command Processing Flow

## End-to-end pipeline

1. `KafkaUpdatesConsumer` получает `TelegramUpdateEnvelope`.
2. `OrchestratorPipeline` загружает `SessionContext` из Redis.
3. `TelegramUpdateNormalizer` превращает payload в `OrchestratorCommand`.
4. `DeduplicatingCommandProcessor` проверяет dedup key.
5. `OrchestratorCommandDispatcher` выбирает handler.
6. `GameCommandHandlers` либо возвращает локальную ошибку/guard result, либо вызывает `game` API.
7. `present_orchestrator_result()` формирует текст и клавиатуру.
8. `TelegramSenderClient` отправляет сообщение.
9. Pipeline сохраняет `last_bot_message_id`, `reply_action_hint` и при необходимости ставит новый таймер.

## Источники команд

- slash-команды;
- reply-keyboard labels;
- inline callback data.

### Важные нормализации

- `/create_lobby <bet>` -> `group_open`
- `/group_start` и `/start_round` -> `group_start`
- `/join <bet>` -> `group_join`
- `Присоединиться (100)` -> `group_join` с `bet=100`
- `/stop` в `single` -> `single_stop`, в `group` -> `group_stop`
- `Начать игру` маршрутизируется через `reply_action_hint`

## Local guards до game API

Для `player_action` orchestrator заранее проверяет:
- `turn_version` не устарел;
- actor совпадает с `current_player_telegram_id`;
- действие входит в `available_moves`.

Это уменьшает число лишних round-trip и делает UX-понятнее.

## Cleanup и UX семантика

- предыдущее сообщение состояния игры удаляется только после успешного хода текущего игрока;
- невалидные `player_action` не должны стирать актуальное сообщение состояния;
- timer notice отправляется только при реально примененном timeout.

## Timer flow

1. После успешного хода pipeline может отменить старый timeout текущего turn_version.
2. Если в snapshot есть `current_timer`, планируется новый timeout task.
3. `RedisTimerWorker` claim-ит задачу, вызывает executor и помечает done key.
4. stale/no-op timeout задачи должны оставаться тихими без ложного Telegram notice.

## Ошибки и устойчивость

- unsupported input завершается без dispatch;
- duplicate update short-circuit-ится через dedup result;
- transport errors к `game` маппятся в `transport_error` и user-facing retry message;
- stale turn от `game` может сопровождаться refresh local context.
