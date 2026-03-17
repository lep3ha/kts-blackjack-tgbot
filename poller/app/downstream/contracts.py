"""Downstream message contracts for broker publishing."""
from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict

from app.telegram.types import TelegramUpdate


class TelegramUpdateEnvelope(BaseModel):
    """Envelope published for a single Telegram update."""

    schema_version: int = 1
    event_name: str = "telegram.update.received"
    update_id: int
    update_type: str
    source_key: str
    partition_key: str
    next_offset: int
    received_at: datetime
    payload: TelegramUpdate

    model_config = ConfigDict(extra="forbid")