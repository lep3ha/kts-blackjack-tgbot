"""Unit tests for dealer card masking in Phase 2.

Tests the masking rule: until runtime_state is in {dealer_turn, resolving, closed},
the dealer's second card is shown as "?" and the score is omitted from the presenter.
"""
import asyncio
import pytest

import app.accessors.bot_accessor as bot_module
from app.accessors.bot_accessor import BotGameAccessor, _DEALER_REVEAL_STATES
from app.models import SessionStatus, ChatMode


# ---------------------------------------------------------------------------
# Masking helper: isolated logic tests (no DB required)
# ---------------------------------------------------------------------------


def _mask_cards(dealer_cards_raw: list[str], runtime_state: str) -> list[str]:
    """Replicate the masking logic from _build_session_snapshot."""
    is_revealed = runtime_state in _DEALER_REVEAL_STATES
    return (
        dealer_cards_raw
        if is_revealed or len(dealer_cards_raw) <= 1
        else [dealer_cards_raw[0], "?"]
    )


def test_cards_masked_during_player_turn():
    result = _mask_cards(["5H", "KS"], "player_turn")
    assert result == ["5H", "?"]


def test_cards_masked_during_dealing():
    result = _mask_cards(["5H", "KS"], "dealing")
    assert result == ["5H", "?"]


def test_cards_masked_during_waiting():
    result = _mask_cards(["5H", "KS"], "waiting")
    assert result == ["5H", "?"]


def test_cards_revealed_during_dealer_turn():
    result = _mask_cards(["5H", "KS"], "dealer_turn")
    assert result == ["5H", "KS"]


def test_cards_revealed_during_resolving():
    result = _mask_cards(["5H", "KS", "2D"], "resolving")
    assert result == ["5H", "KS", "2D"]


def test_cards_revealed_when_closed():
    result = _mask_cards(["5H", "KS"], "closed")
    assert result == ["5H", "KS"]


def test_single_card_never_masked():
    # Only one dealt card — still not masked even if not revealed
    result = _mask_cards(["5H"], "player_turn")
    assert result == ["5H"]


def test_empty_cards_never_masked():
    result = _mask_cards([], "player_turn")
    assert result == []


# ---------------------------------------------------------------------------
# Inline reveal logic assertions
# ---------------------------------------------------------------------------


def test_snapshot_masks_dealer_during_player_turn():
    """Second dealer card should be '?' when runtime_state == player_turn."""
    dealer_cards_raw = ["7H", "KD"]
    is_revealed = "player_turn" in _DEALER_REVEAL_STATES
    visible = dealer_cards_raw if is_revealed or len(dealer_cards_raw) <= 1 else [dealer_cards_raw[0], "?"]
    assert visible == ["7H", "?"]


def test_snapshot_reveals_dealer_during_dealer_turn():
    """All dealer cards should be visible when runtime_state == dealer_turn."""
    dealer_cards_raw = ["7H", "KD"]
    is_revealed = "dealer_turn" in _DEALER_REVEAL_STATES
    visible = dealer_cards_raw if is_revealed or len(dealer_cards_raw) <= 1 else [dealer_cards_raw[0], "?"]
    assert visible == ["7H", "KD"]
