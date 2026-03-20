from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.routing.models import OrchestratorResult

from app.sender.models import OutboundMessage
from app.sender.models import ParseMode
from app.sender.models import UiButton
from app.sender.models import UiKeyboard


DEFAULT_BET = 100


def present_orchestrator_result(
    chat_id: str,
    result: OrchestratorResult,
    *,
    chat_type: str | None = None,
    target_username: str | None = None,
    target_telegram_id: str | None = None,
    target_first_name: str | None = None,
) -> OutboundMessage:
    data = result.data if isinstance(result.data, dict) else None

    if result.success:
        text, keyboard = _present_success(result=result, data=data)
        text, parse_mode = _apply_group_reply_targeting(
            text=text,
            keyboard=keyboard,
            chat_type=chat_type,
            target_username=target_username,
            target_telegram_id=target_telegram_id,
            target_first_name=target_first_name,
        )
        return OutboundMessage(chat_id=chat_id, text=text, keyboard=keyboard, parse_mode=parse_mode)

    text, keyboard = _present_error(result=result, data=data)
    text, parse_mode = _apply_group_reply_targeting(
        text=text,
        keyboard=keyboard,
        chat_type=chat_type,
        target_username=target_username,
        target_telegram_id=target_telegram_id,
        target_first_name=target_first_name,
    )
    return OutboundMessage(chat_id=chat_id, text=text, keyboard=keyboard, parse_mode=parse_mode)


def _apply_group_reply_targeting(
    *,
    text: str,
    keyboard: UiKeyboard | None,
    chat_type: str | None,
    target_username: str | None,
    target_telegram_id: str | None,
    target_first_name: str | None,
) -> tuple[str, ParseMode | None]:
    if keyboard is None or keyboard.kind != "reply":
        return text, None

    if chat_type != "group":
        return text, None

    if isinstance(target_username, str) and target_username:
        if text.startswith("@"):
            return text, None
        return f"@{target_username} {text}", None

    if not (isinstance(target_telegram_id, str) and target_telegram_id):
        return text, None

    display_name = target_first_name.strip() if isinstance(target_first_name, str) else ""
    mention_text = html.escape(display_name or "игрок")
    mention = f'<a href="tg://user?id={target_telegram_id}">{mention_text}</a>'
    if text.startswith("<a href=\"tg://user?id="):
        return text, "HTML"

    return f"{mention} {text}", "HTML"


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

    if result.command_type == "player_balance":
        bank = _format_int(data.get("bank") if data else None)
        if bank is not None:
            return f"Текущий баланс: {bank}.", _build_registration_keyboard()
        return "Не удалось получить баланс.", _build_registration_keyboard()

    if result.command_type in {"group_open", "group_join"}:
        bet = _extract_lobby_bet(data) or DEFAULT_BET
        return _build_lobby_message(data), _build_group_lobby_inline_keyboard(bet=bet)

    if result.command_type == "single_stop":
        chat_mode = str(data.get("chat_mode")) if data and data.get("chat_mode") is not None else "single"
        return _build_game_over_message(data), _build_post_game_keyboard(chat_mode=chat_mode)

    if _is_closed_session(data):
        chat_mode = str(data.get("chat_mode")) if data and data.get("chat_mode") is not None else "single"
        return _build_game_over_message(data), _build_post_game_keyboard(chat_mode=chat_mode)

    if result.command_type in {"group_start", "single_start", "player_action", "current_session"}:
        keyboard = _build_action_inline_keyboard(data)
        if keyboard is None:
            keyboard = _build_session_keyboard(data)
        return _build_game_state_message(data), keyboard

    chat_mode = str(data.get("chat_mode")) if data and data.get("chat_mode") is not None else "single"
    return "Команда выполнена.", _build_post_game_keyboard(chat_mode=chat_mode)


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
        chat_mode = str(data.get("chat_mode")) if data and data.get("chat_mode") is not None else "single"
        return (
            "Нужная игровая сущность не найдена. Сначала зарегистрируй игрока или открой новую сессию.",
            _build_post_game_keyboard(chat_mode=chat_mode),
        )

    if result.error_code == "state_conflict":
        return (
            "Действие не подходит к текущему состоянию игры.",
            _build_session_keyboard(data),
        )

    if result.error_code == "game_logic_error":
        return (
            "Действие нарушает правила игры.",
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
    current_hand_index = current_player.get("hand_index") if current_player else None
    if not isinstance(current_hand_index, int):
        current_hand_index = data.get("current_hand_index") if isinstance(data.get("current_hand_index"), int) else None
    hand_suffix = f" (Рука {int(current_hand_index) + 1})" if isinstance(current_hand_index, int) else ""
    current_username = (
        current_player.get("username")
        or current_player.get("display_name")
        or current_player.get("first_name")
    ) if current_player else None

    if current_username:
        lines = [f"Раунд: {runtime_state} | Ход: {current_username}{hand_suffix}"]
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
            "1) Нажми «Открыть лобби», чтобы создать лобби.\n"
            "2) Игроки присоединяются кнопкой «Присоединиться».\n"
            "3) Когда все готовы, нажми «Начать игру», чтобы запустить раунд."
        )

    return (
        "Как играть:\n"
        "1) Нажми «Начать игру».\n"
        "2) Используй кнопки Hit/Stand/Double/Split/Insurance во время хода.\n"
        "3) Проверяй состояние кнопкой «Текущая»."
    )


def _build_tutorial_keyboard(*, chat_type: str) -> UiKeyboard:
    start_text = "Создать лобби" if chat_type == "group" else "Начать игру"
    return UiKeyboard(
        kind="reply",
        rows=[
            [UiButton(id="balance", title="Баланс", action="Баланс")],
            [UiButton(id="start_game", title=start_text, action=start_text, style="primary")],
        ],
    )


def _build_group_lobby_inline_keyboard(*, bet: int) -> UiKeyboard:
    return UiKeyboard(
        kind="inline",
        rows=[
            [UiButton(id="join", title=f"Присоединиться (ставка: {bet})", action=f"session:join:{bet}", style="primary")],
            [UiButton(id="start_round", title="Начать игру", action="session:start:group", style="secondary")],
        ],
    )


def _build_registration_keyboard() -> UiKeyboard:
    return UiKeyboard(
        kind="reply",
        rows=[
            [UiButton(id="start", title="Начать игру", action="Начать игру", style="primary")],
            [UiButton(id="current", title="Текущая", action="Текущая")],
            [UiButton(id="balance", title="Баланс", action="Баланс")],
        ],
    )


def _build_post_game_keyboard(*, chat_mode: str) -> UiKeyboard:
    is_group = chat_mode == "group"
    return UiKeyboard(
        kind="inline",
        rows=[
            [
                UiButton(
                    id="create_session" if is_group else "start_single",
                    title="Создать сессию" if is_group else "Начать игру",
                    action="session:create:group" if is_group else "session:create:single",
                    style="primary",
                )
            ],
        ],
    )


def _build_session_keyboard(data: dict[str, Any] | None) -> UiKeyboard:
    session_status = data.get("session_status") if isinstance(data, dict) else None
    chat_mode = data.get("chat_mode") if isinstance(data, dict) else None

    if session_status == "in_progress":
        leave_action = "Выйти"
        return UiKeyboard(
            kind="reply",
            rows=[
                [UiButton(id="balance", title="Баланс", action="Баланс")],
                [UiButton(id="leave", title="Выйти", action=leave_action, style="danger")],
                [UiButton(id="current", title="Текущая", action="Текущая")],
            ],
        )

    return UiKeyboard(
        kind="reply",
        rows=[
            [UiButton(id="balance", title="Баланс", action="Баланс")],
            [
                UiButton(
                    id="open_lobby" if chat_mode == "group" else "start_single",
                    title="Создать лобби" if chat_mode == "group" else "Начать игру",
                    action="Создать лобби" if chat_mode == "group" else "Начать игру",
                    style="primary",
                )
            ],
        ],
    )


_ACTION_TITLES: dict[str, str] = {
    "hit": "Hit",
    "stand": "Stand",
    "double": "Double",
    "split": "Split",
    "insurance": "Insurance",
}


def _build_action_inline_keyboard(data: dict[str, Any] | None) -> UiKeyboard | None:
    if not data:
        return None

    available_moves = data.get("available_moves")
    turn_version = data.get("turn_version")
    current_player = data.get("current_player") if isinstance(data.get("current_player"), dict) else {}
    hand_index = current_player.get("hand_index") if isinstance(current_player.get("hand_index"), int) else None
    if hand_index is None and isinstance(data.get("current_hand_index"), int):
        hand_index = data.get("current_hand_index")
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
                    action=(
                        f"action:{move}:tv:{turn_version}:hand:{hand_index}"
                        if hand_index is not None
                        else f"action:{move}:tv:{turn_version}"
                    ),
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
    current_hand_index = current_player.get("hand_index") if isinstance(current_player.get("hand_index"), int) else None
    if current_hand_index is None and isinstance(data.get("current_hand_index"), int):
        current_hand_index = data.get("current_hand_index")

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
        insurance_bet = participant.get("insurance_bet")
        cards = participant.get("cards")
        hands = participant.get("hands") if isinstance(participant.get("hands"), list) else None

        line = f"{marker}{username}"
        if bet is not None:
            line += f" | Ставка: {bet}"
        if not include_results and isinstance(insurance_bet, int) and insurance_bet > 0:
            line += f" | Страховка: {insurance_bet}"
        if bank is not None:
            line += f" | Банк: {bank}"
        has_split_hands = bool(isinstance(hands, list) and len(hands) > 1)
        if not has_split_hands and isinstance(cards, list) and cards:
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

            insurance_delta = participant.get("insurance_delta")
            if isinstance(insurance_delta, int) and insurance_delta != 0:
                insurance_delta_str = f"+{insurance_delta}" if insurance_delta >= 0 else str(insurance_delta)
                line += f" | Страховка: {insurance_delta_str}"

            hand_settlements = participant.get("hand_settlements")
            hand_breakdown = _format_hand_settlements(hand_settlements)
            if hand_breakdown:
                line += f" | {hand_breakdown}"

        lines.append(line)

        if has_split_hands:
            lines.extend(
                _format_split_hands(
                    hands=hands,
                    is_current_player=telegram_id == current_player_id,
                    current_hand_index=current_hand_index,
                )
            )

    return lines


def _format_split_hands(
    *,
    hands: list[Any],
    is_current_player: bool,
    current_hand_index: int | None,
) -> list[str]:
    lines: list[str] = []
    for hand in hands:
        if not isinstance(hand, dict):
            continue

        hand_index = hand.get("hand_index")
        hand_no = int(hand_index) + 1 if isinstance(hand_index, int) and hand_index >= 0 else None
        cards = hand.get("cards")

        line = "   "
        if hand_no is not None:
            line += f"Рука {hand_no}"
        else:
            line += "Рука"

        if isinstance(cards, list) and cards:
            line += f": {' '.join(str(card) for card in cards)}"
            points = _format_hand_points(cards)
            if points:
                line += f" | Очки: {points}"

        if is_current_player and current_hand_index is not None and hand_index == current_hand_index:
            line += " | текущая"

        lines.append(line)

    return lines


def _format_available_moves(data: dict[str, Any]) -> str:
    available_moves = data.get("available_moves")
    if not isinstance(available_moves, list):
        return ""
    return ", ".join(str(move) for move in available_moves)


def _format_hand_settlements(hand_settlements: Any) -> str:
    if not isinstance(hand_settlements, list) or not hand_settlements:
        return ""

    chunks: list[str] = []
    for entry in hand_settlements:
        if not isinstance(entry, dict):
            continue

        hand_index = entry.get("hand_index")
        hand_no = int(hand_index) + 1 if isinstance(hand_index, int) and hand_index >= 0 else None
        result = entry.get("result") if isinstance(entry.get("result"), str) else None
        delta = entry.get("delta") if isinstance(entry.get("delta"), int) else None
        if hand_no is None and result is None and delta is None:
            continue

        text = f"Рука {hand_no}" if hand_no is not None else "Рука"
        if result is not None:
            text += f": {result}"
        if delta is not None:
            delta_str = f"+{delta}" if delta >= 0 else str(delta)
            text += f" ({delta_str})"
        chunks.append(text)

    return "; ".join(chunks)


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
