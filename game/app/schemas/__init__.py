"""Pydantic schemas for Blackjack HTTP API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PlayerCreateRequest(BaseModel):
    telegram_id: str = Field(min_length=1, max_length=64)
    username: Optional[str] = Field(default=None, min_length=1, max_length=64)
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    bank: int = Field(ge=0)


class DeckCreateRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    meta: dict[str, Any] = Field(default_factory=dict)


class SessionCreateRequest(BaseModel):
    deck_id: int = Field(gt=0)
    count_players: int = Field(default=8, ge=1, le=8)


class SeatCreateRequest(BaseModel):
    player_id: int = Field(gt=0)
    position: int = Field(ge=1, le=8)
    bet: int = Field(gt=0)


class ActionRequest(BaseModel):
    position: int = Field(ge=1, le=8)
    action: str = Field(pattern="^(hit|stand|double)$")


class TimeoutRequest(BaseModel):
    position: Optional[int] = Field(default=None, ge=1, le=8)


class GroupLobbyOpenRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    chat_type: str = Field(pattern="^group$")
    actor_telegram_id: str = Field(min_length=1, max_length=64)
    actor_username: Optional[str] = Field(default=None, min_length=1, max_length=64)
    actor_first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    actor_is_admin: bool
    bet: int = Field(gt=0)
    count_players: int = Field(default=8, ge=1, le=8)


class GroupLobbyJoinRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    chat_type: str = Field(pattern="^group$")
    actor_telegram_id: str = Field(min_length=1, max_length=64)
    actor_username: Optional[str] = Field(default=None, min_length=1, max_length=64)
    actor_first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    bet: int = Field(gt=0)


class GroupLobbyStartRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    chat_type: str = Field(pattern="^group$")
    actor_telegram_id: str = Field(min_length=1, max_length=64)
    actor_username: Optional[str] = Field(default=None, min_length=1, max_length=64)
    actor_first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    actor_is_admin: bool


class SingleSessionStartRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    chat_type: str = Field(pattern="^single$")
    actor_telegram_id: str = Field(min_length=1, max_length=64)
    actor_username: Optional[str] = Field(default=None, min_length=1, max_length=64)
    actor_first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    bet: int = Field(gt=0)


class GroupPlayerStopRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    chat_type: str = Field(pattern="^group$")
    actor_telegram_id: str = Field(min_length=1, max_length=64)
    actor_username: Optional[str] = Field(default=None, min_length=1, max_length=64)
    actor_first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)


class SingleSessionStopRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    chat_type: str = Field(pattern="^single$")
    actor_telegram_id: str = Field(min_length=1, max_length=64)
    actor_username: Optional[str] = Field(default=None, min_length=1, max_length=64)
    actor_first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)


class BotSessionQueryRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    chat_type: str = Field(pattern="^(group|single)$")


class BotActionRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    chat_type: str = Field(pattern="^(group|single)$")
    actor_telegram_id: str = Field(min_length=1, max_length=64)
    actor_username: Optional[str] = Field(default=None, min_length=1, max_length=64)
    actor_first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    action: str = Field(pattern="^(hit|stand|double)$")
    turn_version: int = Field(ge=0)


class BotTimeoutRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    chat_type: str = Field(pattern="^(group|single)$")
    turn_version: int = Field(ge=0)


class GroupLobbyQueryRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)


class PlayerStateResponse(BaseModel):
    player_id: int
    position: int
    bet: int
    cards: list[str]
    bank: int


class GroupParticipantResponse(BaseModel):
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    display_name: Optional[str] = None
    player_id: int
    position: int
    participant_status: str
    bet: int
    cards: list[str]
    bank: int
    result: Optional[str] = None
    delta: Optional[int] = None


class CurrentPlayerResponse(BaseModel):
    telegram_id: str
    position: int


class DealerSnapshotResponse(BaseModel):
    cards: list[str]
    is_final: bool
    is_revealed: bool = False


class LobbySnapshotResponse(BaseModel):
    count_players: int
    participants_count: int
    can_start: bool
    start_error: Optional[str] = None


class SummarySnapshotResponse(BaseModel):
    participants_count: int
    results_count: int
    total_delta: int


class GroupSessionSnapshotResponse(BaseModel):
    chat_id: str
    chat_mode: str
    session_id: int
    session_status: str
    runtime_state: str
    turn_version: int
    current_player: Optional[CurrentPlayerResponse] = None
    dealer: DealerSnapshotResponse
    lobby: Optional[LobbySnapshotResponse] = None
    summary: Optional[SummarySnapshotResponse] = None
    available_moves: list[str] = Field(default_factory=list)
    current_position: Optional[int]
    current_timer: Optional[datetime]
    dealer_cards: list[str] = Field(default_factory=list)
    participants: list[GroupParticipantResponse] = Field(default_factory=list)
    can_start: bool
    start_error: Optional[str] = None


class GroupSessionSnapshotCanonicalResponse(BaseModel):
    """Canonical bot-facing session snapshot without legacy compatibility fields."""

    chat_id: str
    chat_mode: str
    session_id: int
    session_status: str
    runtime_state: str
    turn_version: int
    current_player: Optional[CurrentPlayerResponse] = None
    dealer: DealerSnapshotResponse
    lobby: Optional[LobbySnapshotResponse] = None
    summary: Optional[SummarySnapshotResponse] = None
    available_moves: list[str] = Field(default_factory=list)
    current_timer: Optional[datetime]
    participants: list[GroupParticipantResponse] = Field(default_factory=list)


class SessionStateResponse(BaseModel):
    session_id: int
    deck_id: int
    status: str
    state: str
    available_moves: list[str] = Field(default_factory=list)
    current_position: Optional[int]
    current_timer: Optional[datetime]
    dealer_cards: list[str]
    players: list[PlayerStateResponse]


class PlayerCreateResponse(BaseModel):
    id: int
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    bank: int


class DeckCreateResponse(BaseModel):
    id: int
    chat_id: str
    meta: dict[str, Any]


class SessionCreateResponse(BaseModel):
    id: int
    deck_id: int
    status: str
    count_players: int


class SeatCreateResponse(BaseModel):
    session_id: int
    player_id: int
    position: int
    bet: int


class AdminTopupRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    amount: int = Field(gt=0)


class AdminBanRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class AdminTopupResponse(BaseModel):
    username: str
    new_bank: int


class AdminBanResponse(BaseModel):
    username: str
    is_banned: bool
