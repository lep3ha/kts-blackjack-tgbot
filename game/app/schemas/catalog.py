"""Schemas for catalog and direct session APIs."""
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
    action: str = Field(pattern="^(hit|stand|double|split|insurance)$")
    hand_index: Optional[int] = Field(default=None, ge=0)


class TimeoutRequest(BaseModel):
    position: Optional[int] = Field(default=None, ge=1, le=8)


class PlayerStateResponse(BaseModel):
    player_id: int
    position: int
    bet: int
    cards: list[str]
    bank: int


class SessionStateResponse(BaseModel):
    session_id: int
    deck_id: int
    status: str
    state: str
    available_moves: list[str] = Field(default_factory=list)
    current_position: Optional[int]
    current_hand_index: Optional[int] = None
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
