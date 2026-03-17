import pytest


@pytest.fixture
def sample_message_update() -> dict:
    return {
        "update_id": 101,
        "message": {
            "chat": {"id": 777},
            "from": {"id": 555},
            "text": "hello",
        },
    }


@pytest.fixture
def sample_user_only_update() -> dict:
    return {
        "update_id": 202,
        "inline_query": {
            "from": {"id": 4242},
            "query": "ping",
        },
    }
