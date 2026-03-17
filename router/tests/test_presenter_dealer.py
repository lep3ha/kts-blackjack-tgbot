"""Tests for dealer card display in presenter (Phase 2: masking).

_format_dealer must:
- Hide score when cards contain "?" (masked state)
- Show score when all cards are real (revealed state)
"""

from app.sender.presenter import _format_dealer


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
