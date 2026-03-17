from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.routing.models import OrchestratorResult

from app.sender.models import OutboundMessage
from app.sender.models import UiButton
from app.sender.models import UiKeyboard


DEFAULT_BET = 100


def present_orchestrator_result(chat_id: str, result: OrchestratorResult) -> OutboundMessage:
    data = result.data if isinstance(result.data, dict) else None

    if result.success:
        text, keyboard = _present_success(result=result, data=data)
        return OutboundMessage(chat_id=chat_id, text=text, keyboard=keyboard)

    text, keyboard = _present_error(result=result, data=data)
    return OutboundMessage(chat_id=chat_id, text=text, keyboard=keyboard)


def _present_success(
    *,
    result: OrchestratorResult,
    data: dict[str, Any] | None,
) -> tuple[str, UiKeyboard | None]:
    if result.command_type == "tutorial":
        chat_type = str(data.get("chat_type")) if data and data.get("chat_type") is not None else "single"
        return _build_tutorial_message(chat_type=chat_type), _build_tutorial_keyboard(chat_type=chat_type)

    if result.command_type == "admin_topup":
        username = data.get("username") if data else None
        new_bank = _format_int(data.get("new_bank") if data else None)
        if isinstance(username, str) and new_bank is not None:
            return f"Баланс @{username} обновлен: {new_bank}.", None
        return "Баланс игрока обновлен.", None

    if result.command_type == "admin_ban":
        username = data.get("username") if data else None
        if isinstance(username, str) and username:
            return f"Игрок @{username} забанен.", None
        return "Игрок забанен.", None

    if result.command_type == "player_register":
        bank = _format_int(data.get("bank") if data else None)
        text = "Игрок зарегистрирован."
        if bank is not None:
            text = f"Игрок зарегистрирован. Баланс: {bank}."
        return text, _build_registration_keyboard()

    if result.command_type in {"group_open", "group_join"}:
        bet = _extract_lobby_bet(data) or DEFAULT_BET
        return _build_lobby_message(data), _build_group_lobby_keyboard(bet=bet)

    if result.command_type == "single_stop":
        return _build_game_over_message(data), _build_post_game_keyboard()

    if _is_closed_session(data):
        return _build_game_over_message(data), _build_post_game_keyboard()

    if result.command_type in {"group_start", "single_start", "player_action", "current_session"}:
        keyboard = _build_action_inline_keyboard(data)
        if keyboard is None:
            keyboard = _build_session_keyboard(data)
        return _build_game_state_message(data), keyboard

    return "Команда выполнена.", _build_post_game_keyboard()


def _present_error(
    *,
    result: OrchestratorResult,
    data: dict[str, Any] | None,
) -> tuple[str, UiKeyboard | None]:
    if result.error_code == "stale_turn":
        return (
            "Ход устарел. Обнови состояние через /current и попробуй снова.",
            _build_session_keyboard(data),
        )

    if result.error_code == "not_your_turn":
        return (
            "Сейчас ход другого игрока. Дождись своей очереди.",
            _build_session_keyboard(data),
        )

    if result.error_code == "invalid_local_action":
        return (
            "Это действие сейчас недоступно. Обнови состояние через /current.",
            _build_session_keyboard(data),
        )

    if result.error_code == "authorization_error":
        return (
            "Недостаточно прав для этого действия.",
            _build_session_keyboard(data),
        )

    if result.error_code == "not_found":
        return (
            "Нужная игровая сущность не найдена. Сначала зарегистрируй игрока или открой новую сессию.",
            _build_post_game_keyboard(),
        )

    if result.error_code == "state_conflict":
        return (
            result.message or "Действие не подходит к текущему состоянию игры.",
            _build_session_keyboard(data),
        )

    if result.error_code == "game_logic_error":
        return (
            result.message or "Действие нарушает правила игры.",
            _build_session_keyboard(data),
        )

    if result.error_code in {"transport_error", "internal_error"}:
        return (
            "Игровой сервис временно недоступен. Попробуй снова через несколько секунд.",
            _build_session_keyboard(data),
        )

    return result.message or "Не удалось обработать команду.", _build_session_keyboard(data)


def _build_lobby_message(data: dict[str, Any] | None) -> str:
    if not data:
        return "Лобби обновлено."

    lobby = data.get("lobby") if isinstance(data.get("lobby"), dict) else {}
    participants_count = _format_int(lobby.get("participants_count")) or "?"
    count_players = _format_int(lobby.get("count_players")) or "?"
    can_start = lobby.get("can_start") is True
    start_error = lobby.get("start_error")

    participants = _format_participants(data)
    lines = [
        f"Лобби открыто: {participants_count}/{count_players} игроков.",
    ]
    if participants:
        lines.append("")
        lines.append("Участники:")
        lines.extend(participants)

    total_bank = _players_total_bank(data)
    if total_bank is not None:
        lines.append("")
        lines.append(f"Общий счет игроков: {total_bank}")

    lines.append("")
    if can_start:
        lines.append("Игра готова к старту. Нажми «Начать игру».")
    elif isinstance(start_error, str) and start_error:
        lines.append(f"Пока не стартуем: {start_error}")
    else:
        lines.append("Используй /join <ставка>, чтобы добавить игрока.")

    return "\n".join(lines)


def _build_game_state_message(data: dict[str, Any] | None) -> str:
    if not data:
        return "Состояние игры обновлено."

    runtime_state = data.get("runtime_state") or "неизвестно"
    current_player = data.get("current_player") if isinstance(data.get("current_player"), dict) else {}
    current_username = (
        current_player.get("username")
        or current_player.get("display_name")
        or current_player.get("first_name")
    ) if current_player else None

    if current_username:
        lines = [f"Раунд: {runtime_state} | Ход: {current_username}"]
    else:
        lines = [f"Раунд: {runtime_state}"]

    timer_line = _format_timer(data.get("current_timer"))
    if timer_line:
        lines.append(timer_line)

    dealer_line = _format_dealer(data)
    if dealer_line:
        lines.append("")
        lines.append(dealer_line)

    participants = _format_participants(data)
    if participants:
        lines.append("")
        lines.append("Игроки:")
        lines.extend(participants)

    return "\n".join(lines)


def _build_game_over_message(data: dict[str, Any] | None) -> str:
    if not data:
        return "Игра завершена."

    lines = ["Игра завершена."]

    dealer_line = _format_dealer(data)
    if dealer_line:
        lines.append(dealer_line)

    participants = _format_participants(data, include_results=True)
    if participants:
        lines.append("")
        lines.extend(participants)

    return "\n".join(lines)


def _build_tutorial_message(*, chat_type: str) -> str:
    if chat_type == "group":
        return (
            "Как играть:\n"
            "1) Нажми «Начать игру», чтобы открыть лобби.\n"
            "2) Игроки присоединяются кнопкой «Присоединиться».\n"
            "3) Когда все готовы, нажми «Начать игру» ещё раз, чтобы запустить раунд."
        )

    return (
        "Как играть:\n"
        "1) Нажми «Начать игру».\n"
        "2) Используй кнопки Hit/Stand/Double во время хода.\n"
        "3) Проверяй состояние кнопкой «Текущая»."
    )


def _build_tutorial_keyboard(*, chat_type: str) -> UiKeyboard:
    start_text = "Начать игру"
    return UiKeyboard(
        kind="reply",
        rows=[
            [UiButton(id="start_game", title=start_text, action=start_text, style="primary")],
            [UiButton(id="current", title="Текущая", action="Текущая")],
        ],
    )


def _build_group_lobby_keyboard(*, bet: int) -> UiKeyboard:
    return UiKeyboard(
        kind="reply",
        rows=[
            [UiButton(id="join", title=f"Присоединиться ({bet})", action=f"/join {bet}", style="primary")],
            [UiButton(id="start_round", title="Начать игру", action="Начать игру")],
            [UiButton(id="current", title="Текущая", action="Текущая")],
        ],
    )


def _build_registration_keyboard() -> UiKeyboard:
    return UiKeyboard(
        kind="reply",
        rows=[
            [UiButton(id="start", title="Начать игру", action="Начать игру", style="primary")],
            [UiButton(id="current", title="Текущая", action="Текущая")],
        ],
    )


def _build_post_game_keyboard() -> UiKeyboard:
    return UiKeyboard(
        kind="reply",
        rows=[
            [UiButton(id="start", title="Начать игру", action="Начать игру", style="primary")],
            [UiButton(id="current", title="Текущая", action="Текущая")],
        ],
    )


def _build_session_keyboard(data: dict[str, Any] | None) -> UiKeyboard:
    session_status = data.get("session_status") if isinstance(data, dict) else None
    chat_mode = data.get("chat_mode") if isinstance(data, dict) else None

    if chat_mode == "single":
        return UiKeyboard(
            kind="reply",
            rows=[
                [UiButton(id="current", title="Текущая", action="Текущая")],
                [UiButton(id="stop", title="Остановить игру", action="Остановить игру", style="danger")],
            ],
        )

    if session_status == "in_progress":
        return UiKeyboard(
            kind="reply",
            rows=[
                [UiButton(id="current", title="Текущая", action="Текущая")],
                [UiButton(id="group_stop", title="Выйти из раунда", action="Выйти из раунда", style="danger")],
            ],
        )

    return UiKeyboard(
        kind="reply",
        rows=[
            [UiButton(id="current", title="Текущая", action="Текущая")],
            [UiButton(id="start_round", title="Начать игру", action="Начать игру")],
        ],
    )


_ACTION_TITLES: dict[str, str] = {
    "hit": "Hit",
    "stand": "Stand",
    "double": "Double",
}


def _build_action_inline_keyboard(data: dict[str, Any] | None) -> UiKeyboard | None:
    if not data:
        return None

    available_moves = data.get("available_moves")
    turn_version = data.get("turn_version")
    if not isinstance(available_moves, list) or not isinstance(turn_version, int):
        return None

    rows: list[list[UiButton]] = []
    for move in available_moves:
        if not isinstance(move, str):
            continue

        rows.append(
            [
                UiButton(
                    id=move,
                    title=_ACTION_TITLES.get(move, move.capitalize()),
                    action=f"action:{move}:tv:{turn_version}",
                    style="primary" if move == "hit" else "danger" if move == "double" else "secondary",
                )
            ]
        )

    if not rows:
        return None

    return UiKeyboard(kind="inline", rows=rows)


def _format_dealer(data: dict[str, Any]) -> str:
    dealer = data.get("dealer")
    if isinstance(dealer, dict):
        cards = dealer.get("cards")
        if isinstance(cards, list):
            rendered_cards = " ".join(str(card) for card in cards)
            if "?" in cards:
                return f"Дилер: {rendered_cards}"
            points = _format_hand_points(cards)
            return f"Дилер: {rendered_cards} | Очки: {points}" if points else f"Дилер: {rendered_cards}"

    dealer_cards = data.get("dealer_cards")
    if isinstance(dealer_cards, list):
        rendered_cards = " ".join(str(card) for card in dealer_cards)
        if "?" in dealer_cards:
            return f"Дилер: {rendered_cards}"
        points = _format_hand_points(dealer_cards)
        return f"Дилер: {rendered_cards} | Очки: {points}" if points else f"Дилер: {rendered_cards}"

    return ""


def _format_participants(
    data: dict[str, Any],
    *,
    include_results: bool = False,
) -> list[str]:
    participants_raw = data.get("participants")
    current_player = data.get("current_player") if isinstance(data.get("current_player"), dict) else {}
    current_player_id = current_player.get("telegram_id")

    if not isinstance(participants_raw, list):
        return []

    lines: list[str] = []
    for participant in participants_raw:
        if not isinstance(participant, dict):
            continue

        telegram_id = participant.get("telegram_id", "?")
        username = participant.get("username") or participant.get("display_name") or participant.get("first_name") or telegram_id
        marker = "-> " if telegram_id == current_player_id else "   "
        bet = participant.get("bet")
        bank = participant.get("bank")
        cards = participant.get("cards")

        line = f"{marker}{username}"
        if bet is not None:
            line += f" | Ставка: {bet}"
        if bank is not None:
            line += f" | Банк: {bank}"
        if isinstance(cards, list) and cards:
            line += f" | {' '.join(str(card) for card in cards)}"
            points = _format_hand_points(cards)
            if points:
                line += f" | Очки: {points}"

        if include_results:
            result = participant.get("result")
            delta = participant.get("delta")
            if result is not None:
                line += f" | {result}"
            if delta is not None:
                delta_str = f"+{delta}" if delta >= 0 else str(delta)
                line += f" ({delta_str})"

        lines.append(line)

    return lines


def _format_available_moves(data: dict[str, Any]) -> str:
    available_moves = data.get("available_moves")
    if not isinstance(available_moves, list):
        return ""
    return ", ".join(str(move) for move in available_moves)


def _extract_lobby_bet(data: dict[str, Any] | None) -> int | None:
    if not data:
        return None

    participants = data.get("participants")
    if not isinstance(participants, list):
        return None

    for participant in participants:
        if not isinstance(participant, dict):
            continue
        bet = participant.get("bet")
        parsed = _format_int(bet)
        if parsed is not None:
            return int(parsed)
    return None


def _players_total_bank(data: dict[str, Any] | None) -> int | None:
    if not isinstance(data, dict):
        return None

    participants = data.get("participants")
    if not isinstance(participants, list):
        return None

    total = 0
    has_any_bank = False
    for participant in participants:
        if not isinstance(participant, dict):
            continue
        bank = participant.get("bank")
        if isinstance(bank, int):
            total += bank
            has_any_bank = True

    return total if has_any_bank else None


def _format_hand_points(cards: list[Any]) -> str | None:
    total = 0
    aces = 0
    has_unknown = False

    for card in cards:
        if not isinstance(card, str):
            continue

        raw_card = card.strip()
        if not raw_card:
            continue
        if raw_card == "?":
            has_unknown = True
            continue

        rank = _extract_rank(raw_card)
        if rank is None:
            continue

        if rank == "A":
            total += 11
            aces += 1
        elif rank in {"K", "Q", "J", "T"}:
            total += 10
        else:
            total += int(rank)

    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    if total == 0 and not has_unknown:
        return None
    if has_unknown:
        return f"{total}+?"
    return str(total)


def _extract_rank(card: str) -> str | None:
    if card == "?":
        return None

    upper = card.upper()
    if len(upper) >= 3 and upper.startswith("10"):
        return "10"

    rank = upper[0]
    if rank in {"A", "K", "Q", "J", "T"}:
        return rank
    if rank in {"2", "3", "4", "5", "6", "7", "8", "9"}:
        return rank
    return None


def _format_timer(current_timer: Any) -> str | None:
    """Format ISO datetime to 'Осталось: MM:SS' countdown."""
    if not isinstance(current_timer, str):
        return None

    normalized = current_timer.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        deadline = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    else:
        deadline = deadline.astimezone(timezone.utc)

    now = datetime.now(timezone.utc)
    remaining = deadline - now

    if remaining.total_seconds() <= 0:
        return "Осталось: 00:00"

    total_seconds = int(remaining.total_seconds())
    minutes = total_seconds // 60
    seconds = total_seconds % 60

    return f"Осталось: {minutes:02d}:{seconds:02d}"


def _format_int(value: Any) -> str | None:
    if isinstance(value, int):
        return str(value)
    return None


def _is_closed_session(data: dict[str, Any] | None) -> bool:
    return isinstance(data, dict) and data.get("session_status") == "closed"
