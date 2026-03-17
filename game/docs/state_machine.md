# State Machine Blackjack

## Runtime-Состояния
Реализованы в `app/services/blackjack_service.py`:
- `waiting` (initial)
- `dealing`
- `player_turn`
- `dealer_turn`
- `resolving`
- `closed` (final)

## SessionStatus (persisted lifecycle)
Persisted-статус сессии в БД (`SessionStatus`, хранится в `game_sessions.status`):
- `lobby_open` — лобби открыто, игроки могут присоединяться/садиться
- `in_progress` — игра/раунд в процессе (включая runtime-фазы `dealing`, `player_turn`, `dealer_turn`, `resolving`)
- `stopped` — досрочно остановлена (админ/контракт bot stop)
- `closed` — финальное закрытие

`dealing`, `dealer_turn` и `resolving` являются транзиентными runtime-фазами, которыми управляет state chart.

## State Mapping (runtime ↔ persisted)

Runtime state machine и persisted `SessionStatus` решают разные задачи:
- runtime state (`waiting/dealing/player_turn/...`) нужен для точного управления переходами и авто-дренажа фаз.
- persisted status (`lobby_open/in_progress/stopped/closed`) нужен для внешнего жизненного цикла и восстановления из БД.

Типичное соответствие:
- `waiting` → `lobby_open`
- `dealing/player_turn/dealer_turn/resolving` → `in_progress`
- `closed` → `closed`
- `stopped` не является runtime state chart фазой — это внешний persisted-статус.

## События
- `start_round`
- `finish_deal`
- `player_move`
- `timeout_turn`
- `play_dealer`
- `finalize_round`

## Runtime-Пайплайн События
Для каждого события в state machine используется один и тот же цикл:
1. `prepare_event` формирует контекст через `EventContextBuilder`.
2. Validators (`validate_*`) проверяют допустимость события.
3. Guards (`keeps_same_turn`, `advances_to_*`) выбирают ветку перехода.
4. Action callback (`apply_*`, `run_dealer_turn`, `settle_round`) сохраняет эффект через repository.

Такой пайплайн делает поведение предсказуемым: подготовка контекста, решение, эффект.

## Карта Переходов
1. `waiting --start_round--> dealing`
2. `dealing --finish_deal--> player_turn`, если есть хотя бы одна игровая рука
3. `dealing --finish_deal--> dealer_turn`, если игровых рук нет
4. `player_turn --player_move(hit with projected_score < 21)--> player_turn` (та же позиция)
5. `player_turn --player_move(stand|double|hit bust/21)--> player_turn` (следующая позиция)
6. `player_turn --player_move(last playable hand ends)--> dealer_turn`
7. `player_turn --timeout_turn--> player_turn` или `dealer_turn` в зависимости от следующей игровой позиции
8. `dealer_turn --play_dealer--> resolving`
9. `resolving --finalize_round--> closed`

После каждого пользовательского события сервис автоматически дренирует терминальные фазы:
- Если состояние стало `dealer_turn`, сразу выполняется ход дилера.
- Если состояние стало `resolving`, сразу выполняется settlement.

## Guards И Validators
Основные валидационные хуки:
- `validate_can_start`: требуются игроки и persisted-статус сессии `lobby_open`.
- `validate_player_move`: действие должно быть из `hit|stand|double`, активный ход должен совпадать с позицией, рука должна быть игровой.
- `validate_timeout_request`: только активный игрок и только после истечения таймера.

Основные условия ветвления:
- `has_players_to_act`
- `keeps_same_turn`
- `advances_to_next_player`
- `advances_to_dealer`

## Контракт Доступности Событий
`available_events()` возвращает список переходов, которые разрешены из текущего состояния state chart.

Перед выполнением изменяющих операций сервис проверяет доступность события:
- `apply_action()` требует доступности `player_move`.
- `handle_timeout()` требует доступности `timeout_turn`.

Если событие недоступно, клиент получает validation error с:
- идентификатором отклоненного события
- идентификатором текущего состояния
- списком разрешенных событий

## Действия И Побочные Эффекты
Callback-и переходов сохраняют все изменения через `BlackjackRepository`:
- раздача карт
- назначение хода и таймера
- применение действия игрока
- обработка timeout
- добор карт дилером
- settlement раунда и обновление балансов игроков

Дополнительно после рефакторинга:
- `apply_player_move` использует `PlayerActionDispatcher`,
- dispatcher переводит action-контекст в унифицированный payload для `persist_player_move`,
- сервис не ветвится вручную по `hit/stand/double`.

Все callback-и выполняются в границах одной транзакции на одну публичную операцию:
- при успехе: commit
- при ошибке: rollback

## Журнал Состояний (`states` table)
Типичные значения `action`, которые пишет repository:
- `deal`
- `deal_dealer`
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

Каждая строка включает `position`, `action`, временную метку и опциональный JSON-пейлоад `details`.

`details` формируется в dispatch/persistence слое и может содержать:
- `actor`,
- `card`,
- `next_position`,
- `new_bet`.
