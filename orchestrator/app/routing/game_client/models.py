from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel
from pydantic import ConfigDict


ChatType = Literal["group", "single"]
PlayerActionType = Literal["hit", "stand", "double"]


class GroupOpenRequest(BaseModel):
    chat_id: str
    chat_type: Literal["group"] = "group"
    actor_telegram_id: str
    actor_username: str | None = None
    actor_first_name: str | None = None
    actor_is_admin: bool = True
    bet: int
    count_players: int = 8


class GroupStartRequest(BaseModel):
    chat_id: str
    chat_type: Literal["group"] = "group"
    actor_telegram_id: str
    actor_username: str | None = None
    actor_first_name: str | None = None
    actor_is_admin: bool = True


class GroupJoinRequest(BaseModel):
    chat_id: str
    chat_type: Literal["group"] = "group"
    actor_telegram_id: str
    actor_username: str | None = None
    actor_first_name: str | None = None
    bet: int


class GroupPlayerStopRequest(BaseModel):
    chat_id: str
    chat_type: Literal["group"] = "group"
    actor_telegram_id: str
    actor_username: str | None = None
    actor_first_name: str | None = None


class SingleStartRequest(BaseModel):
    chat_id: str
    chat_type: Literal["single"] = "single"
    actor_telegram_id: str
    actor_username: str | None = None
    actor_first_name: str | None = None
    bet: int


class SingleStopRequest(BaseModel):
    chat_id: str
    chat_type: Literal["single"] = "single"
    actor_telegram_id: str
    actor_username: str | None = None
    actor_first_name: str | None = None


class RegisterPlayerRequest(BaseModel):
    telegram_id: str
    username: str | None = None
    first_name: str | None = None
    bank: int


class PlayerActionRequest(BaseModel):
    chat_id: str
    chat_type: ChatType
    actor_telegram_id: str
    actor_username: str | None = None
    actor_first_name: str | None = None
    action: PlayerActionType
    turn_version: int


class TimeoutTurnRequest(BaseModel):
    chat_id: str
    chat_type: ChatType
    turn_version: int


class CurrentSessionRequest(BaseModel):
    chat_id: str
    chat_type: ChatType


class AdminTopupRequest(BaseModel):
    username: str
    amount: int


class AdminBanRequest(BaseModel):
    username: str


class GameErrorCode(StrEnum):
    BAD_REQUEST = "bad_request"
    BAD_JSON = "bad_json"
    VALIDATION_ERROR = "validation_error"
    AUTHORIZATION_ERROR = "authorization_error"
    NOT_FOUND = "not_found"
    STATE_CONFLICT = "state_conflict"
    STALE_TURN = "stale_turn"
    GAME_LOGIC_ERROR = "game_logic_error"
    INTERNAL_ERROR = "internal_error"
    UNKNOWN = "unknown"


class GameServiceError(BaseModel):
    code: GameErrorCode
    message: str
    details: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


class GameServiceEnvelope(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    error: GameServiceError | None = None

    model_config = ConfigDict(extra="allow")