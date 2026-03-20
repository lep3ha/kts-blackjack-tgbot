from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TimeoutTask:
    chat_id: str
    chat_type: str
    session_id: int
    turn_version: int
    due_at: datetime
    hand_index: int | None = None

    @property
    def timer_id(self) -> str:
        return f"{self.chat_id}:{self.session_id}:{self.turn_version}"
