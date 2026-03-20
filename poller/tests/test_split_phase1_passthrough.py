from app.downstream.envelope import build_update_envelope


def test_callback_data_with_hand_segment_is_preserved_in_envelope_payload() -> None:
    update = {
        "update_id": 1001,
        "callback_query": {
            "id": "cb-1",
            "from": {"id": 42, "is_bot": False, "first_name": "A"},
            "message": {
                "message_id": 1,
                "chat": {"id": 777, "type": "private"},
                "date": 1700000000,
                "text": "state",
            },
            "chat_instance": "ci",
            "data": "action:hit:tv:7:hand:1",
        },
    }

    envelope = build_update_envelope(update)

    assert envelope.update_type == "callback_query"
    assert envelope.payload["callback_query"]["data"] == "action:hit:tv:7:hand:1"
