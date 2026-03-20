"""Tests for dealer card display in presenter (Phase 2: masking).

_format_dealer must:
- Hide score when cards contain "?" (masked state)
- Show score when all cards are real (revealed state)
"""

from app.sender.presenter import _format_dealer
from app.sender.presenter import _build_game_state_message
from app.sender.presenter import _format_participants


def test_masked_cards_no_score():
    data = {"dealer": {"cards": ["5H", "?"], "is_final": False, "is_revealed": False}}
    result = _format_dealer(data)
    assert "очки" not in result
    assert "5H" in result
    assert "?" in result


def test_revealed_cards_with_score():
    data = {"dealer": {"cards": ["5H", "KS"], "is_final": False, "is_revealed": True}}
    result = _format_dealer(data)
    assert "Очки" in result
    assert "5H" in result
    assert "KS" in result


def test_revealed_cards_ace_score():
    data = {"dealer": {"cards": ["AH", "6S"], "is_final": True, "is_revealed": True}}
    result = _format_dealer(data)
    assert "Очки: 17" in result


def test_masked_single_card_shown():
    # Only one card (pre-deal state): no mask needed
    data = {"dealer": {"cards": ["7D"], "is_final": False, "is_revealed": False}}
    result = _format_dealer(data)
    assert "7D" in result


def test_empty_cards_returns_empty():
    data = {"dealer": {"cards": [], "is_final": False, "is_revealed": False}}
    result = _format_dealer(data)
    assert result == "Дилер: "


def test_legacy_path_masked_no_score():
    """dealer_cards top-level field (legacy) also hides score when masked."""
    data = {"dealer_cards": ["7D", "?"]}
    result = _format_dealer(data)
    assert "очки" not in result
    assert "7D" in result
    assert "?" in result


def test_legacy_path_revealed_with_score():
    data = {"dealer_cards": ["7D", "5H"]}
    result = _format_dealer(data)
    assert "Очки: 12" in result


def test_no_dealer_field_returns_empty():
    result = _format_dealer({})
    assert result == ""


def test_game_state_header_includes_hand_index_when_present():
    text = _build_game_state_message(
        {
            "runtime_state": "player_turn",
            "current_player": {"username": "alice", "hand_index": 1},
            "dealer": {"cards": ["7D", "?"], "is_final": False, "is_revealed": False},
            "participants": [],
        }
    )
    assert "Ход: alice (Рука 2)" in text


def test_game_state_header_uses_top_level_hand_index_when_missing_in_current_player():
    text = _build_game_state_message(
        {
            "runtime_state": "player_turn",
            "current_player": {"username": "alice"},
            "current_hand_index": 1,
            "dealer": {"cards": ["7D", "?"], "is_final": False, "is_revealed": False},
            "participants": [],
        }
    )
    assert "Ход: alice (Рука 2)" in text


def test_participants_include_hand_settlement_breakdown_in_results_mode():
    lines = _format_participants(
        {
            "participants": [
                {
                    "telegram_id": "tg-1",
                    "username": "alice",
                    "result": "mixed",
                    "delta": 0,
                    "hand_settlements": [
                        {"hand_index": 0, "result": "win", "delta": 100},
                        {"hand_index": 1, "result": "lose", "delta": -100},
                    ],
                }
            ]
        },
        include_results=True,
    )

    assert len(lines) == 1
    assert "Рука 1: win (+100)" in lines[0]
    assert "Рука 2: lose (-100)" in lines[0]


def test_participants_show_split_hands_with_current_marker_in_progress():
    lines = _format_participants(
        {
            "current_player": {"telegram_id": "tg-1", "hand_index": 1},
            "participants": [
                {
                    "telegram_id": "tg-1",
                    "username": "alice",
                    "bet": 100,
                    "bank": 1000,
                    "hands": [
                        {
                            "hand_index": 0,
                            "cards": ["8H", "2H"],
                            "participant_status": "inactive",
                        },
                        {
                            "hand_index": 1,
                            "cards": ["8D", "3D"],
                            "participant_status": "active",
                        },
                    ],
                }
            ],
        }
    )

    assert lines[0].startswith("-> alice")
    assert "Рука 1" in lines[1]
    assert "Статус:" not in lines[1]
    assert "Рука 2" in lines[2]
    assert "Статус:" not in lines[2]
    assert "текущая" in lines[2]


def test_participants_mark_current_split_hand_by_top_level_current_hand_index():
    lines = _format_participants(
        {
            "current_player": {"telegram_id": "tg-1"},
            "current_hand_index": 1,
            "participants": [
                {
                    "telegram_id": "tg-1",
                    "username": "alice",
                    "hands": [
                        {"hand_index": 0, "cards": ["8H", "2H"], "participant_status": "inactive"},
                        {"hand_index": 1, "cards": ["8D", "3D"], "participant_status": "active"},
                    ],
                }
            ],
        }
    )

    assert "текущая" in lines[2]


def test_participants_show_split_hands_in_results_mode_too():
    lines = _format_participants(
        {
            "participants": [
                {
                    "telegram_id": "tg-1",
                    "username": "alice",
                    "result": "mixed",
                    "delta": 0,
                    "hands": [
                        {"hand_index": 0, "cards": ["8H", "2H"], "participant_status": "inactive"},
                        {"hand_index": 1, "cards": ["8D", "3D"], "participant_status": "settled"},
                    ],
                }
            ],
        },
        include_results=True,
    )

    assert len(lines) == 3
    assert "Рука 1" in lines[1]
    assert "8H 2H" in lines[1]
    assert "Рука 2" in lines[2]
    assert "8D 3D" in lines[2]


def test_participants_show_insurance_bet_and_delta_in_results_mode():
    lines = _format_participants(
        {
            "participants": [
                {
                    "telegram_id": "tg-1",
                    "username": "alice",
                    "bet": 100,
                    "insurance_bet": 50,
                    "result": "win",
                    "delta": 150,
                    "insurance_delta": 150,
                }
            ]
        },
        include_results=True,
    )

    assert len(lines) == 1
    assert "Страховка: 50" not in lines[0]
    assert "Страховка: +150" in lines[0]
