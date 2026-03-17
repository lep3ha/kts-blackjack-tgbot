"""Schemas for bot-facing game flows and snapshots."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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
