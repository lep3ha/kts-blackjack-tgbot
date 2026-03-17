# Blackjack State Machine

## Runtime states

В `app/services/blackjack_service.py` определены состояния:
- `waiting`
- `dealing`
- `player_turn`
- `dealer_turn`
- `resolving`
- `closed`

## Persisted lifecycle

Persisted `SessionStatus` хранится в `game_sessions.status` и описывает внешний lifecycle:
- `lobby_open`
- `in_progress`
- `stopped`
- `closed`

Runtime state и persisted status решают разные задачи:
- runtime state нужен для выбора переходов state machine;
- persisted status нужен для восстановления и внешних API-контрактов.

## Основные события

- `start_round`
- `finish_deal`
- `player_move`
- `timeout_turn`
- `play_dealer`
- `finalize_round`

## Пайплайн одного события

1. `prepare_event` собирает runtime context.
2. Validators проверяют допустимость операции.
3. Guards выбирают целевую ветку transition.
4. Action callback сохраняет side effects через repository.

## Карта переходов

1. `waiting -> dealing` через `start_round`
2. `dealing -> player_turn` если есть playable игроки
3. `dealing -> dealer_turn` если playable игроков нет
4. `player_turn -> player_turn` после `hit`, если ход остается у того же игрока
5. `player_turn -> player_turn` после завершения руки и перехода к следующему игроку
6. `player_turn -> dealer_turn` когда playable игроков не осталось
7. `dealer_turn -> resolving`
8. `resolving -> closed`

## Validators и guards

### Validators

- `validate_can_start`
- `validate_player_move`
- `validate_timeout_request`

### Guards

- `has_players_to_act`
- `keeps_same_turn`
- `advances_to_next_player`
- `advances_to_dealer`

## Auto-drain terminal phases

После публичных операций сервис автоматически доигрывает terminal phases:
- если после действия состояние стало `dealer_turn`, немедленно выполняется ход дилера;
- если после этого состояние стало `resolving`, немедленно выполняется settlement.

Это ключевая причина, почему bot API часто возвращает уже финальный snapshot после одного пользовательского действия.

## Event availability contract

`available_events()` показывает, какие события допустимы из текущего runtime state. Перед `apply_action()` и `handle_timeout()` сервис проверяет доступность события и отклоняет невозможные переходы до записи в БД.

## Таймерная семантика

- `current_timer` назначается при старте хода active позиции;
- timeout допустим только если таймер реально истек;
- timeout не shortcut-ит state machine, а использует ее обычный переход `timeout_turn`.

## Audit trail

Repository пишет в `states` такие action values, как:
- `deal`
- `turn_started`
- `hit`
- `stand`
- `double`
- `timeout`
- `players_done`
- `dealer_hit`
- `dealer_stand`
- `result`
- `session_closed`
