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
- inline callback `session:join:<bet>` -> `group_join` с `bet=<bet>`
- inline callback `session:start:group` -> `group_start`
- inline callback `session:create:group` -> `group_open`
- inline callback `session:create:single` -> `single_start`
- `/hit`, `/stand`, `/double`, `/split`, `/insurance` -> `player_action`
- `Hit`, `Stand`, `Double`, `Split`, `Insurance` -> `player_action`
- RU-текст для этих 5 action-команд не нормализуется (EN-only для action text)
- `/split`, `Split` -> `player_action` с `action=split`
- inline callback `action:split:tv:<turn_version>[:hand:<hand_index>]` -> `player_action`
- inline callback `action:insurance:tv:<turn_version>[:hand:<hand_index>]` -> `player_action`
- если message/reply action пришел без `tv`/`hand`, normalizer наследует `turn_version` и `current_hand_index` из `SessionContext`
- `/stop` в `single` -> `single_stop`, в `group` -> `group_stop`
- `Закончить`, `Закончить игру`, `Остановить игру` -> chat-aware stop (`single_stop` или `group_stop`)
- `Начать игру` маршрутизируется через `reply_action_hint`

### Insurance result presentation

- в in-progress/state сообщениях может показываться ставка страховки (`insurance_bet`);
- в финальном (`closed`) сообщении показывается только итог страховки (`insurance_delta`), чтобы не дублировать покупку и результат в одной строке.

## Local guards до game API

Для `player_action` orchestrator заранее проверяет:
- `turn_version` присутствует (из callback payload или из `SessionContext`);
- `turn_version` не устарел;
- actor совпадает с `current_player_telegram_id`;
- действие входит в `available_moves`.

Это уменьшает число лишних round-trip и делает UX-понятнее.

## Cleanup и UX семантика

- предыдущее сообщение состояния игры удаляется только после успешного хода текущего игрока;
- невалидные `player_action` не должны стирать актуальное сообщение состояния;
- timer notice отправляется только при реально примененном timeout.
- после закрытия раунда (`closed`/`single_stop`) отображается inline post-game кнопка: `Создать сессию` (group) или `Начать игру` (single).

## Timer flow

1. После успешного хода pipeline может отменить старый timeout текущего turn_version.
2. Если в snapshot есть `current_timer`, планируется новый timeout task.
3. `RedisTimerWorker` claim-ит задачу, вызывает executor и помечает done key.
4. stale/no-op timeout задачи должны оставаться тихими без ложного Telegram notice.

### Split-specific таймерные правила

- callback вида `action:split:tv:<turn_version>:hand:<hand_index>` участвует в той же cancel-semantics: при успешном ходе текущего игрока отменяется timeout именно для этого `turn_version`.
- timeout-notice для split-руки сохраняет hand context в тексте (`Рука N`), чтобы было понятно, к какой руке применился forced stand.
- если timeout уже no-op (игрок/рука к моменту обработки уже `inactive` или `settled`), notice не отправляется.

## Ошибки и устойчивость

- unsupported input завершается без dispatch;
- duplicate update short-circuit-ится через dedup result;
- transport errors к `game` маппятся в `transport_error` и user-facing retry message;
- stale turn от `game` может сопровождаться refresh local context.
