"""Partitioning helpers for routing updates to workers."""
from __future__ import annotations

from zlib import crc32

from app.telegram.types import TelegramUpdate


def resolve_source_key(update: TelegramUpdate) -> str:
    """Resolve a stable source key for ordered processing."""
    chat_id = _first_value(
        update,
        (
            ("message", "chat", "id"),
            ("edited_message", "chat", "id"),
            ("channel_post", "chat", "id"),
            ("edited_channel_post", "chat", "id"),
            ("callback_query", "message", "chat", "id"),
            ("my_chat_member", "chat", "id"),
            ("chat_member", "chat", "id"),
            ("chat_join_request", "chat", "id"),
        ),
    )
    if chat_id is not None:
        return f"chat:{chat_id}"

    user_id = _first_value(
        update,
        (
            ("message", "from", "id"),
            ("edited_message", "from", "id"),
            ("callback_query", "from", "id"),
            ("inline_query", "from", "id"),
            ("chosen_inline_result", "from", "id"),
            ("shipping_query", "from", "id"),
            ("pre_checkout_query", "from", "id"),
            ("poll_answer", "user", "id"),
            ("chat_join_request", "from", "id"),
        ),
    )
    if user_id is not None:
        return f"user:{user_id}"

    update_id = update.get("update_id", "unknown")
    return f"update:{update_id}"


def resolve_partition_index(update: TelegramUpdate, worker_count: int) -> int:
    """Resolve the target worker index for an update."""
    if worker_count <= 0:
        raise ValueError("Worker count must be greater than zero")

    source_key = resolve_source_key(update)
    return crc32(source_key.encode("utf-8")) % worker_count


def _first_value(
    payload: TelegramUpdate,
    paths: tuple[tuple[str, ...], ...],
) -> int | str | None:
    for path in paths:
        current: object = payload
        for segment in path:
            if not isinstance(current, dict) or segment not in current:
                current = None
                break
            current = current[segment]
        if current is not None:
            return current if isinstance(current, (int, str)) else None
    return None
