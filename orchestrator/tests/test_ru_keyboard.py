"""Tests for ReplyKeyboard labels + normalizer mapping."""
import pytest

from app.routing.normalizer import TelegramUpdateNormalizer
from app.sender.presenter import (
    _build_action_inline_keyboard,
    _build_group_lobby_inline_keyboard,
    _build_post_game_keyboard,
    _build_registration_keyboard,
    _build_session_keyboard,
    _present_success,
)
from app.routing.models import OrchestratorResult
from app.upstream.models import TelegramUpdateEnvelope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_message_envelope(text: str, chat_type: str = "private") -> TelegramUpdateEnvelope:
    from datetime import datetime, timezone
    payload = {
        "message": {
            "text": text,
            "chat": {"id": 42, "type": chat_type},
            "from": {"id": 7, "username": "u", "first_name": "F"},
        }
    }
    return TelegramUpdateEnvelope(
        update_id=1,
        update_type="message",
        source_key="42",
        partition_key="42",
        next_offset=2,
        received_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        payload=payload,
    )


def _make_callback_envelope(callback_data: str, chat_type: str = "private") -> TelegramUpdateEnvelope:
    from datetime import datetime, timezone

    payload = {
        "callback_query": {
            "id": "cb-1",
            "from": {"id": 7, "username": "u", "first_name": "F"},
            "message": {
                "message_id": 100,
                "chat": {"id": 42, "type": chat_type},
                "text": "state",
            },
            "data": callback_data,
        }
    }
    return TelegramUpdateEnvelope(
        update_id=1,
        update_type="callback_query",
        source_key="42",
        partition_key="42",
        next_offset=2,
        received_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        payload=payload,
    )


normalizer = TelegramUpdateNormalizer()


# ---------------------------------------------------------------------------
# Normalizer: action text mapping
# ---------------------------------------------------------------------------

def test_en_hit_maps_to_player_action_hit():
    cmd = normalizer.normalize(_make_message_envelope("Hit"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "hit"


def test_en_stand_maps_to_player_action_stand():
    cmd = normalizer.normalize(_make_message_envelope("Stand"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "stand"


def test_en_double_maps_to_player_action_double():
    cmd = normalizer.normalize(_make_message_envelope("Double"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "double"


def test_en_split_maps_to_player_action_split():
    cmd = normalizer.normalize(_make_message_envelope("Split"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "split"


def test_en_insurance_maps_to_player_action_insurance():
    cmd = normalizer.normalize(_make_message_envelope("Insurance"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "insurance"


def test_ru_action_text_is_unsupported():
    for text in ("Ещё", "Стоп", "Двойная", "Сплит", "Страховка"):
        cmd = normalizer.normalize(_make_message_envelope(text))
        assert cmd.command_type == "unsupported"


def test_ru_current_maps_to_current_session():
    cmd = normalizer.normalize(_make_message_envelope("Текущая"))
    assert cmd.command_type == "current_session"


def test_ru_balance_maps_to_player_balance():
    cmd = normalizer.normalize(_make_message_envelope("Баланс"))
    assert cmd.command_type == "player_balance"


def test_ru_stop_maps_to_single_stop():
    cmd = normalizer.normalize(_make_message_envelope("Закончить"))
    assert cmd.command_type == "single_stop"


def test_ru_stop_phrase_maps_to_single_stop_in_private_chat():
    cmd = normalizer.normalize(_make_message_envelope("Закончить игру", chat_type="private"))
    assert cmd.command_type == "single_stop"


def test_ru_stop_phrase_maps_to_group_stop_in_group_chat():
    cmd = normalizer.normalize(_make_message_envelope("Закончить игру", chat_type="group"))
    assert cmd.command_type == "group_stop"


def test_start_game_text_maps_to_group_start_when_lobby_hint_present():
    from app.state.models import SessionContext

    cmd = normalizer.normalize(
        _make_message_envelope("Начать игру", chat_type="group"),
        context=SessionContext(chat_id="42", chat_type="group", reply_action_hint="group_start"),
    )
    assert cmd.command_type == "group_start"


def test_en_text_extra_whitespace_still_matches():
    """Leading/trailing whitespace normalised by strip()."""
    cmd = normalizer.normalize(_make_message_envelope("  Hit  "))
    assert cmd.command_type == "player_action"
    assert cmd.action == "hit"


def test_unknown_ru_text_is_unsupported():
    cmd = normalizer.normalize(_make_message_envelope("Привет"))
    assert cmd.command_type == "unsupported"


# ---------------------------------------------------------------------------
# Normalizer: slash commands still work alongside Russian labels
# ---------------------------------------------------------------------------

def test_slash_hit_still_works():
    cmd = normalizer.normalize(_make_message_envelope("/hit"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "hit"
    assert cmd.turn_version is None


def test_slash_hit_uses_context_turn_version_and_hand_index():
    from app.state.models import SessionContext

    cmd = normalizer.normalize(
        _make_message_envelope("/hit"),
        context=SessionContext(
            chat_id="42",
            chat_type="single",
            turn_version=9,
            current_hand_index=1,
        ),
    )
    assert cmd.command_type == "player_action"
    assert cmd.action == "hit"
    assert cmd.turn_version == 9
    assert cmd.hand_index == 1


def test_slash_split_still_works():
    cmd = normalizer.normalize(_make_message_envelope("/split"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "split"


def test_slash_insurance_still_works():
    cmd = normalizer.normalize(_make_message_envelope("/insurance"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "insurance"


def test_slash_current_still_works():
    cmd = normalizer.normalize(_make_message_envelope("/current"))
    assert cmd.command_type == "current_session"


def test_slash_balance_still_works():
    cmd = normalizer.normalize(_make_message_envelope("/balance"))
    assert cmd.command_type == "player_balance"


def test_slash_start_maps_to_tutorial():
    cmd = normalizer.normalize(_make_message_envelope("/start"))
    assert cmd.command_type == "tutorial"


def test_slash_single_start_maps_to_single_start():
    cmd = normalizer.normalize(_make_message_envelope("/single_start 150"))
    assert cmd.command_type == "single_start"
    assert cmd.bet == 150


def test_slash_group_start_maps_to_group_start():
    cmd = normalizer.normalize(_make_message_envelope("/group_start 200", chat_type="group"))
    assert cmd.command_type == "group_start"
    assert cmd.bet == 200


def test_slash_group_start_in_private_chat_is_unsupported():
    cmd = normalizer.normalize(_make_message_envelope("/group_start 200", chat_type="private"))
    assert cmd.command_type == "unsupported"


def test_start_game_text_maps_to_single_start_in_private_chat():
    cmd = normalizer.normalize(_make_message_envelope("Начать игру", chat_type="private"))
    assert cmd.command_type == "single_start"


def test_start_game_text_maps_to_group_open_in_group_chat():
    cmd = normalizer.normalize(_make_message_envelope("Начать игру", chat_type="group"))
    assert cmd.command_type == "group_open"


def test_create_lobby_text_maps_to_group_open_in_group_chat():
    cmd = normalizer.normalize(_make_message_envelope("Создать лобби", chat_type="group"))
    assert cmd.command_type == "group_open"


def test_create_lobby_text_is_unsupported_in_private_chat():
    cmd = normalizer.normalize(_make_message_envelope("Создать лобби", chat_type="private"))
    assert cmd.command_type == "unsupported"


def test_admin_topup_command_parses_username_and_amount():
    cmd = normalizer.normalize(_make_message_envelope("/admin_topup @alice 500"))
    assert cmd.command_type == "admin_topup"
    assert cmd.admin_target_username == "alice"
    assert cmd.bet == 500


def test_admin_ban_command_parses_username():
    cmd = normalizer.normalize(_make_message_envelope("/admin_ban @alice"))
    assert cmd.command_type == "admin_ban"
    assert cmd.admin_target_username == "alice"


# ---------------------------------------------------------------------------
# Presenter: ReplyKeyboard action values match _RU_TEXT_TO_COMMAND keys
# ---------------------------------------------------------------------------

def _all_reply_actions(*keyboards) -> list[str]:
    actions = []
    for kb in keyboards:
        if kb is None:
            continue
        if kb.kind != "reply":
            continue
        for row in kb.rows:
            for btn in row:
                actions.append(btn.action)
    return actions


def test_group_lobby_keyboard_actions_are_routable():
    kb = _build_group_lobby_inline_keyboard(bet=100)
    assert kb.kind == "inline"
    for btn in (b for row in kb.rows for b in row):
        if btn.title.startswith("Присоединиться") and btn.action.startswith("session:join:"):
            cmd = normalizer.normalize(_make_callback_envelope(btn.action, chat_type="group"))
            assert cmd.command_type == "group_join"
            assert cmd.bet == 100
            continue
        if btn.title == "Начать игру" and btn.action == "session:start:group":
            cmd = normalizer.normalize(_make_callback_envelope(btn.action, chat_type="group"))
            assert cmd.command_type == "group_start"
            continue
        pytest.fail(f"Unexpected lobby inline button action: {btn.action}")


def test_registration_keyboard_actions_are_routable():
    kb = _build_registration_keyboard()
    ru_map = TelegramUpdateNormalizer._RU_TEXT_TO_COMMAND
    for btn in (b for row in kb.rows for b in row):
        if btn.action.startswith("/"):
            continue
        assert btn.action in ru_map or btn.action == "Начать игру", (
            f"Action '{btn.action}' not routable by normalizer"
        )


def test_post_game_keyboard_actions_are_routable():
    kb = _build_post_game_keyboard(chat_mode="single")
    assert kb.kind == "inline"
    assert kb.rows[0][0].title == "Начать игру"

    start_cmd = normalizer.normalize(_make_callback_envelope(kb.rows[0][0].action, chat_type="private"))
    assert start_cmd.command_type == "single_start"


def test_session_keyboard_single_actions_are_routable():
    kb = _build_session_keyboard({"chat_mode": "single", "session_status": "in_progress"})
    ru_map = TelegramUpdateNormalizer._RU_TEXT_TO_COMMAND
    for btn in (b for row in kb.rows for b in row):
        if btn.action.startswith("/"):
            continue
        assert btn.action in ru_map, f"Action '{btn.action}' not in _RU_TEXT_TO_COMMAND"


def test_session_keyboard_group_lobby_actions_are_routable():
    kb = _build_session_keyboard({"chat_mode": "group", "session_status": "lobby_open"})
    ru_map = TelegramUpdateNormalizer._RU_TEXT_TO_COMMAND
    for btn in (b for row in kb.rows for b in row):
        if btn.action.startswith("/"):
            continue
        assert btn.action in ru_map or btn.action == "Начать игру", (
            f"Action '{btn.action}' not routable by normalizer"
        )


# ---------------------------------------------------------------------------
# Presenter: inline keyboard titles are English, action is callback_data
# ---------------------------------------------------------------------------

def test_inline_keyboard_hit_title_is_english():
    kb = _build_action_inline_keyboard({"available_moves": ["hit", "stand"], "turn_version": 5})
    assert kb is not None
    titles = {btn.title for row in kb.rows for btn in row}
    assert "Hit" in titles
    assert "Stand" in titles


def test_inline_keyboard_double_title_is_english():
    kb = _build_action_inline_keyboard({"available_moves": ["hit", "stand", "double"], "turn_version": 3})
    assert kb is not None
    titles = {btn.title for row in kb.rows for btn in row}
    assert "Double" in titles


def test_inline_keyboard_split_title_is_english():
    kb = _build_action_inline_keyboard({"available_moves": ["hit", "stand", "double", "split"], "turn_version": 3})
    assert kb is not None
    titles = {btn.title for row in kb.rows for btn in row}
    assert "Split" in titles


def test_inline_keyboard_insurance_title_is_english():
    kb = _build_action_inline_keyboard({"available_moves": ["insurance"], "turn_version": 3})
    assert kb is not None
    titles = {btn.title for row in kb.rows for btn in row}
    assert "Insurance" in titles


def test_inline_keyboard_action_is_callback_data():
    """Inline button action must still be callback_data format for routing."""
    kb = _build_action_inline_keyboard({"available_moves": ["hit"], "turn_version": 7})
    assert kb is not None
    btn = kb.rows[0][0]
    assert btn.action == "action:hit:tv:7"


def test_inline_keyboard_action_includes_hand_index_when_present():
    kb = _build_action_inline_keyboard(
        {
            "available_moves": ["hit"],
            "turn_version": 7,
            "current_player": {"telegram_id": "tg-1", "hand_index": 1},
        }
    )
    assert kb is not None
    btn = kb.rows[0][0]
    assert btn.action == "action:hit:tv:7:hand:1"


def test_inline_keyboard_action_includes_hand_index_from_top_level_fallback():
    kb = _build_action_inline_keyboard(
        {
            "available_moves": ["hit"],
            "turn_version": 7,
            "current_player": {"telegram_id": "tg-1"},
            "current_hand_index": 1,
        }
    )
    assert kb is not None
    btn = kb.rows[0][0]
    assert btn.action == "action:hit:tv:7:hand:1"


def test_callback_action_with_hand_index_is_parsed() -> None:
    cmd = normalizer.normalize(_make_callback_envelope("action:stand:tv:5:hand:1"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "stand"
    assert cmd.turn_version == 5
    assert cmd.hand_index == 1


def test_callback_action_without_hand_index_keeps_backward_compatibility() -> None:
    cmd = normalizer.normalize(_make_callback_envelope("action:hit:tv:5"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "hit"
    assert cmd.turn_version == 5
    assert cmd.hand_index is None


def test_callback_insurance_action_is_parsed() -> None:
    cmd = normalizer.normalize(_make_callback_envelope("action:insurance:tv:6"))
    assert cmd.command_type == "player_action"
    assert cmd.action == "insurance"
    assert cmd.turn_version == 6


def test_inline_keyboard_kind_is_inline():
    kb = _build_action_inline_keyboard({"available_moves": ["hit"], "turn_version": 1})
    assert kb is not None
    assert kb.kind == "inline"


# ---------------------------------------------------------------------------
# End-to-end: Russian reply text is routed correctly through normalizer
# ---------------------------------------------------------------------------

def test_russian_current_roundtrip():
    """Simulate button press: text = button action → normalizer → command."""
    action = _build_session_keyboard({"chat_mode": "single", "session_status": "in_progress"}).rows[2][0].action
    cmd = normalizer.normalize(_make_message_envelope(action))
    assert cmd.command_type == "current_session"


def test_russian_stop_roundtrip():
    action = _build_session_keyboard({"chat_mode": "single", "session_status": "in_progress"}).rows[1][0].action
    cmd = normalizer.normalize(_make_message_envelope(action))
    assert cmd.command_type == "single_stop"


def test_russian_group_leave_roundtrip():
    action = _build_session_keyboard({"chat_mode": "group", "session_status": "in_progress"}).rows[1][0].action
    cmd = normalizer.normalize(_make_message_envelope(action, chat_type="group"))
    assert cmd.command_type == "group_stop"


def test_russian_join_reply_text_roundtrip_with_bet():
    cmd = normalizer.normalize(_make_message_envelope("Присоединиться (250)", chat_type="group"))
    assert cmd.command_type == "group_join"
    assert cmd.bet == 250


def test_tutorial_success_returns_start_game_keyboard_for_private_chat():
    text, kb = _present_success(
        result=OrchestratorResult(success=True, message="ok", command_type="tutorial", data={"chat_type": "single"}),
        data={"chat_type": "single"},
    )

    assert "Как играть" in text
    assert kb is not None
    assert kb.kind == "reply"
    assert kb.rows[0][0].title == "Баланс"
    assert kb.rows[1][0].title == "Начать игру"


def test_tutorial_success_returns_start_game_keyboard_for_group_chat():
    text, kb = _present_success(
        result=OrchestratorResult(success=True, message="ok", command_type="tutorial", data={"chat_type": "group"}),
        data={"chat_type": "group"},
    )

    assert "лобби" in text
    assert kb is not None
    assert kb.kind == "reply"
    assert kb.rows[0][0].title == "Баланс"
    assert kb.rows[1][0].title == "Создать лобби"


def test_group_lobby_keyboard_uses_start_game_title():
    kb = _build_group_lobby_inline_keyboard(bet=100)
    assert kb.rows[0][0].title == "Присоединиться (ставка: 100)"
    assert kb.rows[1][0].title == "Начать игру"


def test_group_session_keyboard_lobby_has_balance_and_create_lobby_titles():
    kb = _build_session_keyboard({"chat_mode": "group", "session_status": "lobby_open"})
    assert kb.rows[0][0].title == "Баланс"
    assert kb.rows[1][0].title == "Создать лобби"


def test_group_session_keyboard_non_lobby_uses_open_lobby_title():
    kb = _build_session_keyboard({"chat_mode": "group", "session_status": "closed"})
    assert kb.rows[1][0].title == "Создать лобби"


def test_post_game_keyboard_has_create_session_inline_for_group():
    kb = _build_post_game_keyboard(chat_mode="group")
    assert kb.kind == "inline"
    assert kb.rows[0][0].title == "Создать сессию"
    assert kb.rows[0][0].action == "session:create:group"


def test_post_game_keyboard_create_session_callback_maps_to_group_open():
    cmd = normalizer.normalize(_make_callback_envelope("session:create:group", chat_type="group"))
    assert cmd.command_type == "group_open"
