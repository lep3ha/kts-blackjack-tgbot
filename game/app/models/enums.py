import enum


class SessionStatus(enum.Enum):
    lobby_open = "lobby_open"
    in_progress = "in_progress"
    stopped = "stopped"
    closed = "closed"


class ChatMode(enum.Enum):
    group = "group"
    single = "single"


class ParticipantStatus(enum.Enum):
    joined = "joined"
    active = "active"
    inactive = "inactive"
    settled = "settled"
