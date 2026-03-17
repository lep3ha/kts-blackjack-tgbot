from aiohttp import web

from app.accessors import bot_accessor_key, setup_accessors
from app.accessors.bot_accessor import _DEALER_REVEAL_STATES
from app.core.config import Settings
from app.schemas import DealerSnapshotResponse, GroupSessionSnapshotCanonicalResponse, GroupSessionSnapshotResponse


def test_legacy_schema_contains_legacy_fields():
    assert "dealer_cards" in GroupSessionSnapshotResponse.model_fields
    assert "current_position" in GroupSessionSnapshotResponse.model_fields
    assert "can_start" in GroupSessionSnapshotResponse.model_fields
    assert "start_error" in GroupSessionSnapshotResponse.model_fields


def test_canonical_schema_does_not_contain_legacy_fields():
    assert "dealer_cards" not in GroupSessionSnapshotCanonicalResponse.model_fields
    assert "current_position" not in GroupSessionSnapshotCanonicalResponse.model_fields
    assert "can_start" not in GroupSessionSnapshotCanonicalResponse.model_fields
    assert "start_error" not in GroupSessionSnapshotCanonicalResponse.model_fields


def test_setup_accessors_wires_bot_snapshot_flag():
    app = web.Application()
    cfg = Settings(bot_snapshot_include_legacy_fields=False)

    setup_accessors(app, cfg=cfg)

    accessor = app[bot_accessor_key]
    assert accessor._include_legacy_fields is False


def test_dealer_snapshot_response_has_is_revealed_field():
    assert "is_revealed" in DealerSnapshotResponse.model_fields


def test_dealer_snapshot_response_is_revealed_defaults_false():
    snap = DealerSnapshotResponse(cards=["5H"], is_final=False)
    assert snap.is_revealed is False


def test_dealer_reveal_states_includes_reveal_phases():
    assert "dealer_turn" in _DEALER_REVEAL_STATES
    assert "resolving" in _DEALER_REVEAL_STATES
    assert "closed" in _DEALER_REVEAL_STATES


def test_dealer_reveal_states_excludes_player_phases():
    assert "player_turn" not in _DEALER_REVEAL_STATES
    assert "waiting" not in _DEALER_REVEAL_STATES
    assert "dealing" not in _DEALER_REVEAL_STATES
