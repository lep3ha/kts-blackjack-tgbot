from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict


TelegramUpdatePayload = dict[str, Any]


class TelegramUpdateEnvelope(BaseModel):
    schema_version: int = 1
    event_name: str = "telegram.update.received"
    update_id: int
    update_type: str
    source_key: str
    partition_key: str
    next_offset: int
    received_at: datetime
    payload: TelegramUpdatePayload

    model_config = ConfigDict(extra="forbid")