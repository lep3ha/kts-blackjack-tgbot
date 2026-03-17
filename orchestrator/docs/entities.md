# Orchestrator Entities And Responsibilities

## `TelegramUpdateEnvelope`

Kafka input contract с полями:
- `update_id`
- `update_type`
- `source_key`
- `partition_key`
- `next_offset`
- `received_at`
- `payload`

## `OrchestratorCommand`

Нормализованная команда для dispatch.

Основные поля:
- `chat_id`, `chat_type`
- `actor_telegram_id`, `actor_username`, `actor_first_name`
- `command_type`
- `bet`
- `action`
- `turn_version`
- `admin_target_username`

## `OrchestratorResult`

Единый результат обработки команды:
- `success`
- `message`
- `command_type`
- `error_code`
- `data`

`presenter` использует его как единственный вход для построения Telegram outbound message.

## `SessionContext`

Redis-сущность короткоживущего chat context.

Поля:
- `session_id`
- `reply_action_hint`
- `turn_version`
- `current_timer`
- `current_player_telegram_id`
- `available_moves`
- `last_bot_message_id`

Назначение:
- контекстная маршрутизация `Начать игру`
- local guards для `player_action`
- cleanup предыдущего сообщения состояния игры

## Dedup сущности

`RedisDedupStore` защищает от повторной обработки update через TTL-ключи, завязанные на `update_id`, `chat_id`, `command_type`, `action`, `actor` и `turn_version`.

## Timer entities

`TimeoutTask` содержит:
- `chat_id`
- `chat_type`
- `session_id`
- `turn_version`
- `due_at`

Redis timer worker использует индекс задач, payload key, claim key и done key для безопасного polling/claim/execute flow.
