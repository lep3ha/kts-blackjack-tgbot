from pydantic import BaseModel


class SessionContext(BaseModel):
    chat_id: str
    chat_type: str
    session_id: int | None = None
    reply_action_hint: str | None = None
    turn_version: int | None = None
    current_hand_index: int | None = None
    current_timer: str | None = None
    current_player_telegram_id: str | None = None
    available_moves: list[str] = []
    last_bot_message_id: int | None = None
