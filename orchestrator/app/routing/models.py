from dataclasses import dataclass, field
from typing import Any
from typing import Literal


ChatType = Literal["group", "single"]
CommandType = Literal[
    "tutorial",
    "group_open",
    "group_start",
    "group_join",
    "group_stop",
    "single_start",
    "single_stop",
    "player_register",
    "player_action",
    "current_session",
    "admin_topup",
    "admin_ban",
    "unsupported",
]
PlayerActionType = Literal["hit", "stand", "double"]


@dataclass(slots=True)
class OrchestratorCommand:
    update_id: int
    chat_id: str
    chat_type: ChatType
    actor_telegram_id: str | None
    actor_username: str | None
    actor_first_name: str | None
    command_type: CommandType
    admin_target_username: str | None = None
    bet: int | None = None
    action: PlayerActionType | None = None
    turn_version: int | None = None
    source_key: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OrchestratorResult:
    success: bool
    message: str
    command_type: CommandType
    error_code: str | None = None
    data: dict[str, Any] | None = None
