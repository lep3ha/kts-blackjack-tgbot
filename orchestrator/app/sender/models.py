from dataclasses import dataclass
from dataclasses import field
from typing import Literal


ButtonStyle = Literal["primary", "secondary", "danger"]
KeyboardKind = Literal["reply", "inline"]
ParseMode = Literal["HTML"]


@dataclass(slots=True)
class UiButton:
    id: str
    title: str
    action: str
    style: ButtonStyle = "secondary"


@dataclass(slots=True)
class UiKeyboard:
    kind: KeyboardKind
    rows: list[list[UiButton]] = field(default_factory=list)


@dataclass(slots=True)
class OutboundMessage:
    chat_id: str
    text: str
    keyboard: UiKeyboard | None = None
    parse_mode: ParseMode | None = None
