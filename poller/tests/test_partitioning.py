from app.runtime.partitioning import resolve_partition_index
from app.runtime.partitioning import resolve_source_key


def test_resolve_source_key_prefers_chat(sample_message_update: dict) -> None:
    assert resolve_source_key(sample_message_update) == "chat:777"


def test_resolve_source_key_falls_back_to_user(sample_user_only_update: dict) -> None:
    assert resolve_source_key(sample_user_only_update) == "user:4242"


def test_resolve_source_key_falls_back_to_update_id() -> None:
    assert resolve_source_key({"update_id": 303}) == "update:303"


def test_partition_index_is_stable_and_bounded(sample_message_update: dict) -> None:
    worker_count = 4
    index_a = resolve_partition_index(sample_message_update, worker_count)
    index_b = resolve_partition_index(sample_message_update, worker_count)
    assert index_a == index_b
    assert 0 <= index_a < worker_count
