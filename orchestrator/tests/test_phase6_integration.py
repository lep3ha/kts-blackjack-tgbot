"""Phase 6: Integration and smoke tests for complete workflows.

Tests the end-to-end flow of:
1. Command normalization → handler dispatch → result presentation
2. Single player game flow (private chat)
3. Group game flow (group chat)
4. UI button routing (reply keyboards + inline buttons)
5. Timer countdown display
6. Error handling and edge cases
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.routing.models import OrchestratorResult
from app.routing.normalizer import TelegramUpdateNormalizer
from app.sender.presenter import present_orchestrator_result
from app.upstream.models import TelegramUpdateEnvelope


# ============================================================================
# Test Fixtures
# ============================================================================

def _make_message_envelope(text: str, chat_id: str = "123", chat_type: str = "private", actor_id: int = 999) -> TelegramUpdateEnvelope:
    """Create a message update envelope for testing."""
    from datetime import datetime, timezone

    payload = {
        "message": {
            "text": text,
            "chat": {"id": int(chat_id), "type": chat_type},
            "from": {"id": actor_id, "username": "testuser", "first_name": "Test"},
        }
    }
    return TelegramUpdateEnvelope(
        update_id=1,
        update_type="message",
        source_key=chat_id,
        partition_key=chat_id,
        next_offset=2,
        received_at=datetime(2026, 3, 17, tzinfo=timezone.utc),
        payload=payload,
    )


def _make_success_result(command_type: str, data: dict | None = None) -> OrchestratorResult:
    """Create a success orchestrator result for testing."""
    return OrchestratorResult(
        success=True,
        message="ok",
        command_type=command_type,
        data=data or {},
    )


def _make_error_result(command_type: str, error_code: str = "invalid") -> OrchestratorResult:
    """Create an error orchestrator result for testing."""
    return OrchestratorResult(
        success=False,
        message="Error occurred",
        command_type=command_type,
        error_code=error_code,
        data={},
    )


# ============================================================================
# Single Player (Private Chat) Workflow Tests
# ============================================================================

class TestSinglePlayerWorkflow:
    """Tests for /single_start → player actions → game over flow."""

    def test_single_start_normalizes_to_command(self):
        """User sends /single_start → normalizer produces single_start command."""
        normalizer = TelegramUpdateNormalizer()
        envelope = _make_message_envelope("/single_start", chat_type="private")
        
        cmd = normalizer.normalize(envelope)
        
        assert cmd.command_type == "single_start"
        assert cmd.chat_type == "single"  # Telegram 'private' normalized to 'single'

    def test_single_start_presents_game_state(self):
        """single_start result displays game state with current player."""
        data = {
            "session_id": 1,
            "chat_mode": "single",
            "runtime_state": "turn",
            "current_player": {"telegram_id": 999, "username": "testuser"},
            "dealer": {"cards": ["10♠", "?"]},
            "participants": [{"telegram_id": 999, "username": "testuser", "cards": ["K♥", "5♦"]}],
            "available_moves": ["hit", "stand"],
            "turn_version": 1,
            "current_timer": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat(),
        }
        result = _make_success_result("single_start", data)
        
        msg = present_orchestrator_result("123", result)
        
        assert "Раунд: turn" in msg.text
        assert "Осталось:" in msg.text  # Timer shown
        assert "testuser" in msg.text
        assert "Дилер:" in msg.text

    def test_player_hit_action_normalizes(self):
        """User clicks Hit button → normalizer produces player_action hit."""
        normalizer = TelegramUpdateNormalizer()
        envelope = _make_message_envelope("Hit", chat_type="private")
        
        cmd = normalizer.normalize(envelope)
        
        assert cmd.command_type == "player_action"
        assert cmd.action == "hit"

    def test_player_stand_action_normalizes(self):
        """User clicks Stand button → normalizer produces player_action stand."""
        normalizer = TelegramUpdateNormalizer()
        envelope = _make_message_envelope("Stand", chat_type="private")
        
        cmd = normalizer.normalize(envelope)
        
        assert cmd.command_type == "player_action"
        assert cmd.action == "stand"

    def test_single_stop_ends_game(self):
        """User clicks Stop button in private chat → single_stop command."""
        normalizer = TelegramUpdateNormalizer()
        envelope = _make_message_envelope("Остановить игру", chat_type="private")
        
        cmd = normalizer.normalize(envelope)
        
        assert cmd.command_type == "single_stop"

    def test_game_over_displays_results(self):
        """Game over result shows dealer, player cards, and deltas."""
        data = {
            "chat_mode": "single",
            "dealer": {"cards": ["10♠", "7♥"]},
            "participants": [
                {"telegram_id": 999, "username": "testuser", "delta": 250}
            ],
        }
        result = _make_success_result("single_stop", data)
        
        msg = present_orchestrator_result("123", result)
        
        assert "Игра завершена" in msg.text
        assert "Дилер:" in msg.text
        assert "testuser" in msg.text
        assert "(+250)" in msg.text  # Delta shown in parentheses

    def test_game_over_displays_per_hand_breakdown_when_present(self):
        """Game over result includes split-hand settlements when provided by game snapshot."""
        data = {
            "chat_mode": "single",
            "dealer": {"cards": ["10♠", "7♥"]},
            "participants": [
                {
                    "telegram_id": 999,
                    "username": "testuser",
                    "result": "mixed",
                    "delta": 0,
                    "hand_settlements": [
                        {"hand_index": 0, "result": "win", "delta": 100},
                        {"hand_index": 1, "result": "lose", "delta": -100},
                    ],
                }
            ],
        }
        result = _make_success_result("single_stop", data)

        msg = present_orchestrator_result("123", result)

        assert "Рука 1: win (+100)" in msg.text
        assert "Рука 2: lose (-100)" in msg.text

    def test_current_session_shows_game_state(self):
        """User sends /current → shows current game state with timer."""
        data = {
            "session_id": 1,
            "chat_mode": "single",
            "runtime_state": "turn",
            "dealer": {"cards": ["K♠", "?"]},
            "participants": [{"telegram_id": 999, "username": "testuser"}],
            "current_timer": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
        }
        result = _make_success_result("current_session", data)
        
        msg = present_orchestrator_result("123", result)
        
        assert "Раунд: turn" in msg.text
        assert "Осталось:" in msg.text


# ============================================================================
# Group Game Workflow Tests
# ============================================================================

class TestGroupGameWorkflow:
    """Tests for /create_lobby → /join → /group_start → group actions → exit."""

    def test_create_lobby_opens_group_game(self):
        """User sends /create_lobby 100 in group → opens lobby with bet."""
        normalizer = TelegramUpdateNormalizer()
        envelope = _make_message_envelope("/create_lobby 100", chat_id="456", chat_type="group")
        
        cmd = normalizer.normalize(envelope)
        
        assert cmd.command_type == "group_open"
        # Amount is parsed separately by the handler layer

    def test_join_lobby_allows_player_entry(self):
        """User sends /join 100 → adds player to existing lobby."""
        normalizer = TelegramUpdateNormalizer()
        envelope = _make_message_envelope("/join 100", chat_id="456", chat_type="group", actor_id=888)
        
        cmd = normalizer.normalize(envelope)
        
        assert cmd.command_type == "group_join"
        # Amount is parsed separately by the handler layer
        assert cmd.actor_telegram_id == "888"  # Stored as string

    def test_join_lobby_button_text_routes_with_bet(self):
        """User clicks reply button 'Присоединиться (100)' → group_join with bet."""
        normalizer = TelegramUpdateNormalizer()
        envelope = _make_message_envelope("Присоединиться (100)", chat_id="456", chat_type="group", actor_id=888)

        cmd = normalizer.normalize(envelope)

        assert cmd.command_type == "group_join"
        assert cmd.bet == 100
        assert cmd.actor_telegram_id == "888"

    def test_group_start_begins_round(self):
        """User sends /group_start → starts game in group lobby."""
        normalizer = TelegramUpdateNormalizer()
        envelope = _make_message_envelope("/group_start", chat_id="456", chat_type="group")
        
        cmd = normalizer.normalize(envelope)
        
        assert cmd.command_type == "group_start"

    def test_group_lobby_displays_participants(self):
        """Lobby state shows participants, total count, and join button."""
        data = {
            "chat_mode": "group",
            "lobby": {
                "participants_count": 2,
                "count_players": 3,
                "can_start": False,
            },
            "participants": [
                {"telegram_id": 999, "username": "alice"},
                {"telegram_id": 888, "username": "bob"},
            ],
        }
        result = _make_success_result("group_open", data)
        
        msg = present_orchestrator_result("456", result)
        
        assert "Лобби открыто: 2/3 игроков" in msg.text
        assert "alice" in msg.text
        assert "bob" in msg.text

    def test_group_game_state_shows_current_player_marker(self):
        """During group game, current player marked with →."""
        data = {
            "chat_mode": "group",
            "runtime_state": "turn",
            "dealer": {"cards": ["9♠", "?"]},
            "participants": [
                {"telegram_id": 999, "username": "alice"},
                {"telegram_id": 888, "username": "bob"},
            ],
            "current_player": {"telegram_id": 999},
            "current_timer": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat(),
        }
        result = _make_success_result("group_start", data)
        
        msg = present_orchestrator_result("456", result)
        
        assert "-> alice" in msg.text  # Current player marked
        assert "   bob" in msg.text    # Other player indented
        assert "Осталось:" in msg.text

    def test_group_stop_exits_player(self):
        """User clicks 'Выйти из раунда' in group → group_stop command."""
        normalizer = TelegramUpdateNormalizer()
        envelope = _make_message_envelope("Выйти из раунда", chat_id="456", chat_type="group", actor_id=999)
        
        cmd = normalizer.normalize(envelope)
        
        assert cmd.command_type == "group_stop"

    def test_group_game_over_shows_all_results(self):
        """Game over in group shows all player deltas (when included in presenter logic)."""
        data = {
            "chat_mode": "group",
            "runtime_state": "finished",
            "dealer": {"cards": ["K♠", "9♥"]},
            "participants": [
                {"telegram_id": 999, "username": "alice", "delta": 500},
                {"telegram_id": 888, "username": "bob", "delta": -250},
            ],
        }
        from app.sender.presenter import _format_participants
        lines = _format_participants(data, include_results=True)
        
        assert "alice" in lines[0]
        assert "(+500)" in lines[0]
        assert "bob" in lines[1]
        assert "(-250)" in lines[1]


# ============================================================================
# UI Button Routing Tests
# ============================================================================

class TestButtonRouting:
    """Tests that UI buttons (reply + inline) route correctly."""

    def test_reply_keyboard_hit_button_routable(self):
        """Hit button text routes to player_action hit."""
        normalizer = TelegramUpdateNormalizer()

        # Russian action aliases are intentionally unsupported.
        cmd1 = normalizer.normalize(_make_message_envelope("Ещё"))
        assert cmd1.command_type == "unsupported"

        # New English button works
        cmd2 = normalizer.normalize(_make_message_envelope("Hit"))
        assert cmd2.command_type == "player_action"
        assert cmd2.action == "hit"

    def test_reply_keyboard_stand_button_routable(self):
        """Stand button uses EN-only action text mapping."""
        normalizer = TelegramUpdateNormalizer()

        cmd1 = normalizer.normalize(_make_message_envelope("Стоп"))
        assert cmd1.command_type == "unsupported"

        cmd2 = normalizer.normalize(_make_message_envelope("Stand"))
        assert cmd2.command_type == "player_action"
        assert cmd2.action == "stand"

    def test_reply_keyboard_double_button_routable(self):
        """Double button uses EN-only action text mapping."""
        normalizer = TelegramUpdateNormalizer()

        cmd1 = normalizer.normalize(_make_message_envelope("Двойная"))
        assert cmd1.command_type == "unsupported"

        cmd2 = normalizer.normalize(_make_message_envelope("Double"))
        assert cmd2.command_type == "player_action"
        assert cmd2.action == "double"

    def test_reply_keyboard_split_button_routable(self):
        """Split button uses EN-only action text mapping."""
        normalizer = TelegramUpdateNormalizer()

        cmd1 = normalizer.normalize(_make_message_envelope("Сплит"))
        assert cmd1.command_type == "unsupported"

        cmd2 = normalizer.normalize(_make_message_envelope("Split"))
        assert cmd2.command_type == "player_action"
        assert cmd2.action == "split"

    def test_inline_keyboard_action_roundtrips(self):
        """Inline button callback action:move:tv:N routes correctly."""
        from app.sender.presenter import _build_action_inline_keyboard
        
        # Create inline keyboard
        kb = _build_action_inline_keyboard({
            "available_moves": ["hit", "stand"],
            "turn_version": 5,
        })
        assert kb is not None
        
        # Extract callback action
        action = kb.rows[0][0].action  # "action:hit:tv:5"
        
        # Verify it routes (in real app, handled by callback_query)
        assert "action:" in action
        assert "tv:" in action


# ============================================================================
# Timer and Message Formatting Tests
# ============================================================================

class TestTimerAndMessaging:
    """Tests timer countdown display and message simplification."""

    def test_timer_countdown_displays_remaining_time(self):
        """Game state shows MM:SS countdown from current_timer deadline."""
        data = {
            "runtime_state": "turn",
            "current_timer": (datetime.now(timezone.utc) + timedelta(minutes=2, seconds=30)).isoformat(),
            "dealer": {},
            "participants": [],
        }
        
        from app.sender.presenter import _build_game_state_message
        text = _build_game_state_message(data)
        
        assert "Осталось: 02:" in text

    def test_message_omits_technical_fields(self):
        """Game state message excludes session_status, turn_version, etc."""
        data = {
            "runtime_state": "turn",
            "session_status": "in_progress",  # Should NOT appear
            "turn_version": 5,  # Should NOT appear
            "dealer": {},
            "participants": [],
        }
        
        from app.sender.presenter import _build_game_state_message
        text = _build_game_state_message(data)
        
        # Check message is clean (no technical fields)
        assert "session_status" not in text
        assert "turn_version" not in text
        assert "Раунд: turn" in text  # Only runtime_state shown

    def test_participant_display_clean_format(self):
        """Participant list shows username with bet, bank, and cards."""
        from app.sender.presenter import _format_participants
        
        data = {
            "participants": [
                {
                    "telegram_id": 1,
                    "username": "alice",
                    "bet": 100,
                    "bank": 500,
                    "cards": ["K♥", "5♦"],
                },
            ],
            "current_player": {"telegram_id": 1},
        }
        
        lines = _format_participants(data)
        
        # Current player marked with arrow; full info displayed
        assert lines[0].startswith("-> alice")
        assert "Ставка: 100" in lines[0]
        assert "Банк: 500" in lines[0]
        assert "K♥" in lines[0]


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests graceful handling of errors in the presenter layer."""

    def test_stale_turn_error_shows_retry_message(self):
        """stale_turn error prompts user to refresh state."""
        result = _make_error_result("player_action", "stale_turn")
        
        msg = present_orchestrator_result("123", result)
        
        assert "Ход устарел" in msg.text

    def test_authorization_error_shows_permission_message(self):
        """authorization_error shows permission denied message."""
        result = _make_error_result("admin_ban", "authorization_error")
        
        msg = present_orchestrator_result("123", result)
        
        assert "Недостаточно прав" in msg.text

    def test_transport_error_shows_retry_message(self):
        """transport/internal failures show retriable user-facing message."""
        result = _make_error_result("current_session", "transport_error")

        msg = present_orchestrator_result("123", result)

        assert "Игровой сервис временно недоступен" in msg.text

    def test_not_your_turn_error_shows_turn_owner_message(self):
        result = _make_error_result("player_action", "not_your_turn")

        msg = present_orchestrator_result("123", result)

        assert "Сейчас ход другого игрока" in msg.text

    def test_invalid_local_action_error_shows_action_unavailable_message(self):
        result = _make_error_result("player_action", "invalid_local_action")

        msg = present_orchestrator_result("123", result)

        assert "действие сейчас недоступно" in msg.text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
