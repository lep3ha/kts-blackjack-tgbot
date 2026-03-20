import unittest
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from sqlalchemy import select
from sqlalchemy import text

from app.core.datetime_utils import utc_now_naive
from app.db import db
from app.main import init_app
from app.models import GameSession, PlayerHand, PlayerToSession
from app.models.enums import ParticipantStatus


class TestBlackjackIntegrationFlow(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        try:
            await db.init()

            # Phase 16 removed runtime create_all, so db.init may no longer
            # touch the database. Integration tests still require a reachable DB.
            async with db.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

            await db.close()
            return await init_app()
        except Exception as exc:
            raise unittest.SkipTest(f"DB is unavailable for integration test: {exc}") from exc

    async def test_full_blackjack_flow_with_db(self):
        suffix = uuid4().hex[:8]

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-{suffix}", "bank": 1000},
        )
        assert player_resp.status == 201
        player_data = await player_resp.json()
        assert player_data["success"] is True
        player_id = player_data["data"]["id"]

        deck_resp = await self.client.request(
            "POST",
            "/decks",
            json={"chat_id": f"chat-{suffix}", "meta": {}},
        )
        assert deck_resp.status == 201
        deck_data = await deck_resp.json()
        assert deck_data["success"] is True
        deck_id = deck_data["data"]["id"]

        session_resp = await self.client.request(
            "POST",
            "/sessions",
            json={"deck_id": deck_id, "count_players": 1},
        )
        assert session_resp.status == 201
        session_data = await session_resp.json()
        assert session_data["success"] is True
        session_id = session_data["data"]["id"]

        seat_resp = await self.client.request(
            "PUT",
            f"/sessions/{session_id}/players",
            json={"player_id": player_id, "position": 1, "bet": 100},
        )
        assert seat_resp.status == 201
        seat_data = await seat_resp.json()
        assert seat_data["success"] is True

        cards = iter(["5H", "6D", "9C", "7S", "2H"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request("PUT", f"/sessions/{session_id}/start")
            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True
            assert start_data["data"]["status"] == "in_progress"
            assert "available_moves" in start_data["data"]

            action_resp = await self.client.request(
                "PUT",
                f"/sessions/{session_id}/actions",
                json={"position": 1, "action": "stand"},
            )
            assert action_resp.status == 200
            action_data = await action_resp.json()
            assert action_data["success"] is True
            assert action_data["data"]["status"] == "closed"
            assert action_data["data"]["available_moves"] == []

        state_resp = await self.client.request("GET", f"/sessions/{session_id}")
        assert state_resp.status == 200
        state_data = await state_resp.json()
        assert state_data["success"] is True
        assert state_data["data"]["status"] == "closed"
        assert state_data["data"]["available_moves"] == []

        openapi_resp = await self.client.request("GET", "/openapi.json")
        assert openapi_resp.status == 200
        openapi_data = await openapi_resp.json()
        assert openapi_data["openapi"] == "3.0.3"
        assert "/sessions/{session_id}/actions" in openapi_data["paths"]

    async def test_group_lobby_bot_flow_with_db(self):
        suffix = uuid4().hex[:8]

        admin_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-admin-{suffix}", "bank": 1000},
        )
        assert admin_resp.status == 201

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-player-{suffix}", "bank": 1000},
        )
        assert player_resp.status == 201

        open_resp = await self.client.request(
            "POST",
            "/bot/sessions/group/open",
            json={
                "chat_id": f"chat-{suffix}",
                "chat_type": "group",
                "actor_telegram_id": f"tg-admin-{suffix}",
                "actor_is_admin": True,
                "bet": 100,
            },
        )
        assert open_resp.status == 201
        open_data = await open_resp.json()
        assert open_data["success"] is True
        assert open_data["data"]["session_status"] == "lobby_open"
        assert len(open_data["data"]["participants"]) == 1

        join_resp = await self.client.request(
            "POST",
            "/bot/sessions/group/join",
            json={
                "chat_id": f"chat-{suffix}",
                "chat_type": "group",
                "actor_telegram_id": f"tg-player-{suffix}",
                "bet": 150,
            },
        )
        assert join_resp.status == 200
        join_data = await join_resp.json()
        assert join_data["success"] is True
        assert len(join_data["data"]["participants"]) == 2

        cards = iter(["5H", "6D", "9C", "7S", "2H", "KD"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/group/start",
                json={
                    "chat_id": f"chat-{suffix}",
                    "chat_type": "group",
                    "actor_telegram_id": f"tg-admin-{suffix}",
                    "actor_is_admin": True,
                },
            )

        assert start_resp.status == 200
        start_data = await start_resp.json()
        assert start_data["success"] is True
        assert start_data["data"]["session_status"] == "in_progress"
        assert start_data["data"]["runtime_state"] == "player_turn"
        assert len(start_data["data"]["participants"]) == 2

    async def test_single_start_bot_flow_with_db(self):
        suffix = uuid4().hex[:8]

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-single-{suffix}", "bank": 1000},
        )
        assert player_resp.status == 201

        cards = iter(["5H", "6D", "9C", "7S"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": f"dm-{suffix}",
                    "chat_type": "single",
                    "actor_telegram_id": f"tg-single-{suffix}",
                    "bet": 100,
                },
            )

        assert start_resp.status == 200
        start_data = await start_resp.json()
        assert start_data["success"] is True
        assert start_data["data"]["chat_mode"] == "single"
        assert start_data["data"]["session_status"] == "in_progress"
        assert start_data["data"]["runtime_state"] == "player_turn"
        assert len(start_data["data"]["participants"]) == 1
        assert start_data["data"]["participants"][0]["participant_status"] == "active"

    async def test_single_stop_bot_flow_with_db(self):
        suffix = uuid4().hex[:8]

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-stop-{suffix}", "bank": 1000},
        )
        assert player_resp.status == 201

        # Make settlement deterministic: dealer draws 8D and busts (15 + 8 = 23).
        cards = iter(["10H", "7D", "9C", "6S", "8D"])  # P1: 17; Dealer: 15; Dealer hit: bust
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": f"dm-stop-{suffix}",
                    "chat_type": "single",
                    "actor_telegram_id": f"tg-stop-{suffix}",
                    "bet": 100,
                },
            )
            assert start_resp.status == 200

            stop_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/stop",
                json={
                    "chat_id": f"dm-stop-{suffix}",
                    "chat_type": "single",
                    "actor_telegram_id": f"tg-stop-{suffix}",
                },
            )
        assert stop_resp.status == 200
        stop_data = await stop_resp.json()
        assert stop_data["success"] is True
        assert stop_data["data"]["session_status"] == "closed"
        assert len(stop_data["data"]["dealer"]["cards"]) == 3
        assert stop_data["data"]["participants"][0]["participant_status"] == "settled"
        assert stop_data["data"]["participants"][0]["result"] == "win"

        current_resp = await self.client.request(
            "GET",
            f"/bot/sessions/current?chat_id=dm-stop-{suffix}&chat_type=single",
        )
        assert current_resp.status == 404

    async def test_session_state_uses_active_hand_index_cards(self):
        suffix = uuid4().hex[:8]

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-hand-{suffix}", "bank": 1000},
        )
        assert player_resp.status == 201
        player_data = await player_resp.json()
        player_id = player_data["data"]["id"]

        deck_resp = await self.client.request(
            "POST",
            "/decks",
            json={"chat_id": f"chat-hand-{suffix}", "meta": {}},
        )
        assert deck_resp.status == 201
        deck_data = await deck_resp.json()
        deck_id = deck_data["data"]["id"]

        session_resp = await self.client.request(
            "POST",
            "/sessions",
            json={"deck_id": deck_id, "count_players": 1},
        )
        assert session_resp.status == 201
        session_data = await session_resp.json()
        session_id = session_data["data"]["id"]

        seat_resp = await self.client.request(
            "PUT",
            f"/sessions/{session_id}/players",
            json={"player_id": player_id, "position": 1, "bet": 100},
        )
        assert seat_resp.status == 201

        cards = iter(["10H", "7D", "9C", "6S"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request("PUT", f"/sessions/{session_id}/start")
        assert start_resp.status == 200

        async with db.async_session() as session:
            seat = (
                await session.execute(
                    select(PlayerToSession).where(
                        PlayerToSession.session_id == session_id,
                        PlayerToSession.position == 1,
                    )
                )
            ).scalar_one()

            session_row = (
                await session.execute(select(GameSession).where(GameSession.id == session_id))
            ).scalar_one()
            session_row.current_position = 1
            session_row.current_hand_index = 1

            session.add(
                PlayerHand(
                    player_to_session_id=seat.id,
                    hand_index=1,
                    cards=["AS", "9D"],
                    bet=100,
                    participant_status=ParticipantStatus.active,
                )
            )
            await session.commit()

        state_resp = await self.client.request("GET", f"/sessions/{session_id}")
        assert state_resp.status == 200
        state_data = await state_resp.json()
        assert state_data["success"] is True
        assert state_data["data"]["current_hand_index"] == 1
        assert state_data["data"]["players"][0]["cards"] == ["AS", "9D"]

    async def test_single_action_bot_flow_with_db(self):
        suffix = uuid4().hex[:8]

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-action-{suffix}", "bank": 1000},
        )
        assert player_resp.status == 201

        # Make settlement deterministic: dealer draws 8D and busts (15 + 8 = 23).
        cards = iter(["10H", "7D", "9C", "6S", "8D"])  # P1: 17; Dealer: 15; Dealer hit: bust
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": f"dm-action-{suffix}",
                    "chat_type": "single",
                    "actor_telegram_id": f"tg-action-{suffix}",
                    "bet": 100,
                },
            )
            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True
            turn_version = start_data["data"]["turn_version"]

            action_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": f"dm-action-{suffix}",
                    "chat_type": "single",
                    "actor_telegram_id": f"tg-action-{suffix}",
                    "action": "stand",
                    "turn_version": turn_version,
                },
            )
        assert action_resp.status == 200
        action_data = await action_resp.json()
        assert action_data["success"] is True
        assert action_data["data"]["session_status"] == "closed"
        assert action_data["data"]["participants"][0]["result"] == "win"

    async def test_single_timeout_bot_flow_with_db(self):
        suffix = uuid4().hex[:8]

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-timeout-{suffix}", "bank": 1000},
        )
        assert player_resp.status == 201

        cards = iter(["10H", "7D", "9C", "6S"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": f"dm-timeout-{suffix}",
                    "chat_type": "single",
                    "actor_telegram_id": f"tg-timeout-{suffix}",
                    "bet": 100,
                },
            )
        assert start_resp.status == 200
        start_data = await start_resp.json()
        assert start_data["success"] is True
        turn_version = start_data["data"]["turn_version"]

        with patch(
            "app.services.blackjack_service.utc_now_naive",
            return_value=utc_now_naive() + timedelta(minutes=10),
        ):
            timeout_resp = await self.client.request(
                "POST",
                "/bot/sessions/timeout",
                json={
                    "chat_id": f"dm-timeout-{suffix}",
                    "chat_type": "single",
                    "turn_version": turn_version,
                },
            )

        assert timeout_resp.status == 200
        timeout_data = await timeout_resp.json()
        assert timeout_data["success"] is True
        assert timeout_data["data"]["session_status"] == "closed"
        assert timeout_data["data"]["participants"][0]["participant_status"] == "settled"

    async def test_single_split_requires_playing_second_hand_before_close(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-split-{suffix}"
        chat_id = f"dm-split-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Start: P1 8,8 (split allowed), Dealer 10,6 (will hit once on close),
        # Split draws: first-hand +2, second-hand +3, dealer hit +5.
        cards = iter(["8H", "8D", "10C", "6S", "2H", "3D", "5C"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )

            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True
            assert start_data["data"]["current_hand_index"] == 0
            turn_version = start_data["data"]["turn_version"]

            split_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": turn_version,
                    "hand_index": 0,
                },
            )
            assert split_resp.status == 200
            split_data = await split_resp.json()
            assert split_data["success"] is True
            assert split_data["data"]["session_status"] == "in_progress"
            assert split_data["data"]["current_hand_index"] == 0
            split_participant = split_data["data"]["participants"][0]
            assert len(split_participant["hands"]) == 2
            assert split_participant["hands"][0]["hand_index"] == 0
            assert split_participant["hands"][1]["hand_index"] == 1
            split_turn_version = split_data["data"]["turn_version"]

            first_hand_stand_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": split_turn_version,
                    "hand_index": 0,
                },
            )

            assert first_hand_stand_resp.status == 200
            first_hand_stand_data = await first_hand_stand_resp.json()
            assert first_hand_stand_data["success"] is True
            # Critical invariant: after resolving first split hand the round stays open,
            # and the same player moves to hand #2.
            assert first_hand_stand_data["data"]["session_status"] == "in_progress"
            assert first_hand_stand_data["data"]["current_hand_index"] == 1
            assert first_hand_stand_data["data"]["current_player"]["telegram_id"] == telegram_id
            assert first_hand_stand_data["data"]["current_player"]["hand_index"] == 1
            # Inline actions in orchestrator depend on available_moves from game snapshot.
            # If this list is empty here, user will lose action buttons on hand #2.
            assert first_hand_stand_data["data"]["available_moves"]
            assert "stand" in first_hand_stand_data["data"]["available_moves"]
            first_hand_participant = first_hand_stand_data["data"]["participants"][0]
            assert len(first_hand_participant["hands"]) == 2
            assert first_hand_participant["hands"][0]["participant_status"] == "inactive"
            assert first_hand_participant["hands"][1]["participant_status"] == "active"
            # Red-lock: transition to hand #2 must not overwrite cards of hand #1.
            assert first_hand_participant["hands"][0]["cards"] == ["8H", "2H"]
            assert first_hand_participant["hands"][1]["cards"] == ["8D", "3D"]

            second_turn_version = first_hand_stand_data["data"]["turn_version"]
            second_hand_stand_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": second_turn_version,
                    "hand_index": 1,
                },
            )

        assert second_hand_stand_resp.status == 200
        second_hand_stand_data = await second_hand_stand_resp.json()
        assert second_hand_stand_data["success"] is True
        assert second_hand_stand_data["data"]["session_status"] == "closed"
        assert second_hand_stand_data["data"]["current_hand_index"] is None
        # Red-lock: final split resolution must return result payload, not only closed status.
        final_participant = second_hand_stand_data["data"]["participants"][0]
        assert final_participant["result"] is not None
        assert final_participant["hand_settlements"]

    async def test_split_delays_second_hand_draw_until_hand_becomes_active(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-split-delay-{suffix}"
        chat_id = f"dm-split-delay-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Start: P1 8,8 (split allowed), Dealer 10,6.
        # Expected target behavior:
        # - On split only hand #1 gets a drawn card (+2).
        # - Hand #2 receives its second card (+3) only when it becomes active.
        cards = iter(["8H", "8D", "10C", "6S", "2H", "3D", "5C"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )

            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True
            turn_version = start_data["data"]["turn_version"]

            split_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": turn_version,
                    "hand_index": 0,
                },
            )

            assert split_resp.status == 200
            split_data = await split_resp.json()
            assert split_data["success"] is True
            split_participant = split_data["data"]["participants"][0]
            assert len(split_participant["hands"]) == 2
            assert split_participant["hands"][0]["cards"] == ["8H", "2H"]
            # Red-lock: second hand must not receive a second card before activation.
            assert split_participant["hands"][1]["cards"] == ["8D"]

            first_turn_version = split_data["data"]["turn_version"]
            first_hand_stand_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": first_turn_version,
                    "hand_index": 0,
                },
            )

            assert first_hand_stand_resp.status == 200
            first_hand_stand_data = await first_hand_stand_resp.json()
            assert first_hand_stand_data["success"] is True
            assert first_hand_stand_data["data"]["session_status"] == "in_progress"
            assert first_hand_stand_data["data"]["current_hand_index"] == 1
            first_hand_participant = first_hand_stand_data["data"]["participants"][0]
            assert len(first_hand_participant["hands"]) == 2
            # Red-lock: second card appears only after hand #2 becomes active.
            assert first_hand_participant["hands"][1]["cards"] == ["8D", "3D"]

    async def test_split_aces_both_hands_21_are_auto_resolved_without_timeout(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-split-aces-{suffix}"
        chat_id = f"dm-split-aces-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Start: P1 A,A; Dealer 10,6; split draws Q and Q.
        # Target behavior: after split there are no playable player hands,
        # so service must auto-finish round immediately without waiting for timeout.
        cards = iter(["AH", "AD", "10C", "6S", "QH", "QD", "5C"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )

            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True

            split_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": start_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )

        assert split_resp.status == 200
        split_data = await split_resp.json()
        assert split_data["success"] is True
        # Red-lock: no timeout required if all split hands are terminal right away.
        assert split_data["data"]["session_status"] == "closed"
        assert split_data["data"]["current_hand_index"] is None
        assert split_data["data"]["available_moves"] == []

    async def test_split_second_hand_can_be_resplit_into_third_hand(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-resplit-{suffix}"
        chat_id = f"dm-resplit-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Start: P1 8,8; Dealer 10,6.
        # Split #1 draws: hand0 +2, hand1 delayed +8 (so hand1 can be re-split).
        # Re-split on hand1 draws: hand1 +3, hand2 delayed +4.
        cards = iter(["8H", "8D", "10C", "6S", "2H", "8S", "3C", "4D", "5H"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )
            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True

            split_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": start_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )
            assert split_resp.status == 200
            split_data = await split_resp.json()
            assert split_data["success"] is True

            first_hand_stand_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": split_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )
            assert first_hand_stand_resp.status == 200
            first_hand_data = await first_hand_stand_resp.json()
            assert first_hand_data["success"] is True
            assert first_hand_data["data"]["current_hand_index"] == 1

            resplit_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": first_hand_data["data"]["turn_version"],
                    "hand_index": 1,
                },
            )

        assert resplit_resp.status == 200
        resplit_data = await resplit_resp.json()
        assert resplit_data["success"] is True
        participant = resplit_data["data"]["participants"][0]
        assert len(participant["hands"]) == 3
        assert [hand["hand_index"] for hand in participant["hands"]] == [0, 1, 2]
        assert participant["hands"][1]["cards"] == ["8D", "3C"]
        assert participant["hands"][2]["cards"] == ["8S"]

    async def test_double_split_third_hand_gets_card_on_activation(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-resplit-activate-{suffix}"
        chat_id = f"dm-resplit-activate-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Start: P1 A,A; dealer 9,7.
        # Split #1 draws hand0 +2 and prepares hand1 delayed +A (to allow re-split).
        # Split #2 on hand1 draws hand1 +K (21 terminal) and prepares hand2 delayed +5.
        # Because hand1 is terminal right after split, service auto-advances to hand2
        # inside split handling, where delayed card must be materialized.
        cards = iter(["AH", "AD", "9C", "7S", "2H", "AS", "KH", "5D", "4H"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )
            assert start_resp.status == 200
            start_data = await start_resp.json()

            first_split_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": start_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )
            assert first_split_resp.status == 200
            first_split_data = await first_split_resp.json()
            assert first_split_data["success"] is True

            stand_hand0_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": first_split_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )
            assert stand_hand0_resp.status == 200
            stand_hand0_data = await stand_hand0_resp.json()
            assert stand_hand0_data["success"] is True
            assert stand_hand0_data["data"]["current_hand_index"] == 1

            second_split_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": stand_hand0_data["data"]["turn_version"],
                    "hand_index": 1,
                },
            )
            assert second_split_resp.status == 200
            second_split_data = await second_split_resp.json()

        assert second_split_data["success"] is True
        assert second_split_data["data"]["session_status"] == "in_progress"
        assert second_split_data["data"]["current_hand_index"] == 2
        participant = second_split_data["data"]["participants"][0]
        hand2 = next(hand for hand in participant["hands"] if hand["hand_index"] == 2)
        # Red-lock: auto-advance to hand 3 after terminal split must materialize delayed card.
        assert hand2["cards"] == ["AS", "5D"]

    async def test_split_transition_skips_action_when_next_hand_is_21(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-split-skip-21-{suffix}"
        chat_id = f"dm-split-skip-21-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Start: P1 A,A; dealer 10,6.
        # Split draws hand0 +9 (20), hand1 delayed +K (21).
        # After stand on hand0, hand1 is terminal and must be auto-skipped.
        cards = iter(["AH", "AD", "10C", "6S", "9H", "KC", "5D"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )
            assert start_resp.status == 200
            start_data = await start_resp.json()

            split_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": start_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )
            assert split_resp.status == 200
            split_data = await split_resp.json()
            assert split_data["success"] is True
            assert split_data["data"]["current_hand_index"] == 0

            stand_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": split_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )

        assert stand_resp.status == 200
        stand_data = await stand_resp.json()
        assert stand_data["success"] is True
        # Red-lock: service must not ask action for current hand when its score is already 21.
        assert stand_data["data"]["session_status"] == "closed"
        assert stand_data["data"]["current_hand_index"] is None
        assert stand_data["data"]["available_moves"] == []

    async def test_split_second_hand_hit_keeps_moves_and_allows_finish(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-split-hit-second-{suffix}"
        chat_id = f"dm-split-hit-second-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Start: P1 8,8; dealer 10,6.
        # Split draws hand0 +2 and hand1 delayed +3.
        # After stand on hand0, activate hand1, then hit to 13 and keep same hand active.
        cards = iter(["8H", "8D", "10C", "6S", "2H", "3D", "2C", "5H"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )
            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True

            split_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": start_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )
            assert split_resp.status == 200
            split_data = await split_resp.json()
            assert split_data["success"] is True

            stand_first_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": split_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )
            assert stand_first_resp.status == 200
            stand_first_data = await stand_first_resp.json()
            assert stand_first_data["success"] is True
            assert stand_first_data["data"]["current_hand_index"] == 1

            hit_second_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "hit",
                    "turn_version": stand_first_data["data"]["turn_version"],
                    "hand_index": 1,
                },
            )

            assert hit_second_resp.status == 200
            hit_second_data = await hit_second_resp.json()
            assert hit_second_data["success"] is True
            assert hit_second_data["data"]["session_status"] == "in_progress"
            assert hit_second_data["data"]["current_hand_index"] == 1
            assert "hit" in hit_second_data["data"]["available_moves"]
            assert "stand" in hit_second_data["data"]["available_moves"]

            stand_second_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": hit_second_data["data"]["turn_version"],
                    "hand_index": 1,
                },
            )

        assert stand_second_resp.status == 200
        stand_second_data = await stand_second_resp.json()
        assert stand_second_data["success"] is True
        assert stand_second_data["data"]["session_status"] == "closed"
        assert stand_second_data["data"]["current_hand_index"] is None

    async def test_single_split_second_hand_timeout_closes_round(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-split-timeout-{suffix}"
        chat_id = f"dm-split-timeout-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Start: P1 8,8 (split allowed), Dealer 10,6.
        # Split draws: first-hand +2, second-hand +3, dealer hit +5.
        cards = iter(["8H", "8D", "10C", "6S", "2H", "3D", "5C"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )

            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True
            turn_version = start_data["data"]["turn_version"]

            split_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": turn_version,
                    "hand_index": 0,
                },
            )
            assert split_resp.status == 200
            split_data = await split_resp.json()
            assert split_data["success"] is True

            first_turn_version = split_data["data"]["turn_version"]
            first_hand_stand_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": first_turn_version,
                    "hand_index": 0,
                },
            )

            assert first_hand_stand_resp.status == 200
            first_hand_stand_data = await first_hand_stand_resp.json()
            assert first_hand_stand_data["success"] is True
            assert first_hand_stand_data["data"]["session_status"] == "in_progress"
            assert first_hand_stand_data["data"]["current_hand_index"] == 1

            second_turn_version = first_hand_stand_data["data"]["turn_version"]
            with patch(
                "app.services.blackjack_service.utc_now_naive",
                return_value=utc_now_naive() + timedelta(minutes=10),
            ):
                timeout_resp = await self.client.request(
                    "POST",
                    "/bot/sessions/timeout",
                    json={
                        "chat_id": chat_id,
                        "chat_type": "single",
                        "turn_version": second_turn_version,
                        "hand_index": 1,
                    },
                )

        assert timeout_resp.status == 200
        timeout_data = await timeout_resp.json()
        assert timeout_data["success"] is True
        assert timeout_data["data"]["session_status"] == "closed"
        assert timeout_data["data"]["current_hand_index"] is None
        # Red-lock: timeout on last split hand must still return final result payload.
        final_participant = timeout_data["data"]["participants"][0]
        assert final_participant["result"] is not None
        assert final_participant["hand_settlements"]

    async def test_repeated_split_shifted_last_hand_gets_delayed_card_on_activation(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-resplit-shifted-last-{suffix}"
        chat_id = f"dm-resplit-shifted-last-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Start: P1 8,8; dealer 10,6.
        # Split #1 on hand0: hand0 +8 (resplit possible), hand1 delayed +3.
        # Split #2 on hand0: inserts new hand1 (seed 8 + delayed 4) and shifts old hand1 to hand2.
        # Red-lock: when queue reaches shifted hand2, delayed card +3 must be materialized automatically.
        cards = iter(["8H", "8D", "10C", "6S", "8C", "3D", "2H", "4S", "5C"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )
            assert start_resp.status == 200
            start_data = await start_resp.json()

            split_first_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": start_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )
            assert split_first_resp.status == 200
            split_first_data = await split_first_resp.json()
            assert split_first_data["success"] is True

            split_second_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "split",
                    "turn_version": split_first_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )
            assert split_second_resp.status == 200
            split_second_data = await split_second_resp.json()
            assert split_second_data["success"] is True
            assert split_second_data["data"]["current_hand_index"] == 0

            stand_hand0_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": split_second_data["data"]["turn_version"],
                    "hand_index": 0,
                },
            )
            assert stand_hand0_resp.status == 200
            stand_hand0_data = await stand_hand0_resp.json()
            assert stand_hand0_data["success"] is True
            assert stand_hand0_data["data"]["current_hand_index"] == 1

            stand_hand1_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": stand_hand0_data["data"]["turn_version"],
                    "hand_index": 1,
                },
            )

        assert stand_hand1_resp.status == 200
        stand_hand1_data = await stand_hand1_resp.json()
        assert stand_hand1_data["success"] is True
        assert stand_hand1_data["data"]["current_hand_index"] == 2

        participant = stand_hand1_data["data"]["participants"][0]
        hand2 = next(hand for hand in participant["hands"] if hand["hand_index"] == 2)
        assert hand2["cards"] == ["8D", "3D"]

    async def test_single_insurance_burns_immediately_when_dealer_has_no_blackjack(self):
        suffix = uuid4().hex[:8]
        telegram_id = f"tg-ins-burn-{suffix}"
        chat_id = f"dm-ins-burn-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Player: 10,7. Dealer: A,9 (no blackjack).
        cards = iter(["10H", "7D", "AS", "9C"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )

            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True
            assert "insurance" in start_data["data"]["available_moves"]

            insurance_turn_version = start_data["data"]["turn_version"]
            insurance_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "insurance",
                    "turn_version": insurance_turn_version,
                    "hand_index": 0,
                },
            )

            assert insurance_resp.status == 200
            insurance_data = await insurance_resp.json()
            assert insurance_data["success"] is True
            assert insurance_data["data"]["session_status"] == "in_progress"
            assert "insurance" not in insurance_data["data"]["available_moves"]
            participant_after_insurance = insurance_data["data"]["participants"][0]
            assert participant_after_insurance["bank"] == 950

            stand_turn_version = insurance_data["data"]["turn_version"]
            stand_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": stand_turn_version,
                    "hand_index": 0,
                },
            )

        assert stand_resp.status == 200
        stand_data = await stand_resp.json()
        assert stand_data["success"] is True
        assert stand_data["data"]["session_status"] == "closed"
        participant_after_close = stand_data["data"]["participants"][0]
        assert participant_after_close["bank"] == 850

    async def test_single_insurance_pays_when_dealer_has_blackjack(self):
        suffix = uuid4().hex[:8]
        telegram_id = f"tg-ins-win-{suffix}"
        chat_id = f"dm-ins-win-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 1000},
        )
        assert player_resp.status == 201

        # Player: 10,9. Dealer: A,K (blackjack).
        cards = iter(["10H", "9D", "AS", "KC"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )

            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True
            assert "insurance" in start_data["data"]["available_moves"]

            insurance_turn_version = start_data["data"]["turn_version"]
            insurance_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "insurance",
                    "turn_version": insurance_turn_version,
                    "hand_index": 0,
                },
            )

            assert insurance_resp.status == 200
            insurance_data = await insurance_resp.json()
            assert insurance_data["success"] is True
            assert insurance_data["data"]["session_status"] == "in_progress"
            participant_after_insurance = insurance_data["data"]["participants"][0]
            assert participant_after_insurance["bank"] == 950

            stand_turn_version = insurance_data["data"]["turn_version"]
            stand_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "stand",
                    "turn_version": stand_turn_version,
                    "hand_index": 0,
                },
            )

        assert stand_resp.status == 200
        stand_data = await stand_resp.json()
        assert stand_data["success"] is True
        assert stand_data["data"]["session_status"] == "closed"
        participant_after_close = stand_data["data"]["participants"][0]
        assert participant_after_close["bank"] == 1000

    async def test_single_action_stale_turn_rejected(self):
        suffix = uuid4().hex[:8]

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-stale-{suffix}", "bank": 1000},
        )
        assert player_resp.status == 201

        cards = iter(["9S", "7H", "6D", "8C"])  # keep session in_progress; avoid natural blackjack
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": f"dm-stale-{suffix}",
                    "chat_type": "single",
                    "actor_telegram_id": f"tg-stale-{suffix}",
                    "bet": 100,
                },
            )
        assert start_resp.status == 200
        start_data = await start_resp.json()
        assert start_data["success"] is True
        stale_version = max(start_data["data"]["turn_version"] - 1, 0)

        action_resp = await self.client.request(
            "POST",
            "/bot/sessions/action",
            json={
                "chat_id": f"dm-stale-{suffix}",
                "chat_type": "single",
                "actor_telegram_id": f"tg-stale-{suffix}",
                "action": "stand",
                "turn_version": stale_version,
            },
        )

        assert action_resp.status == 409
        action_data = await action_resp.json()
        assert action_data["success"] is False
        assert action_data["error"]["code"] == "stale_turn"

    async def test_single_double_rejected_when_bank_insufficient_for_double(self):
        suffix = uuid4().hex[:8]

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-double-{suffix}", "bank": 100},
        )
        assert player_resp.status == 201

        # Deal a normal hand (no blackjack) so double is a candidate.
        cards = iter(["9S", "2H", "5D", "6C", "7H"])  # P1: 9S,2H; Dealer: 5D,6C; Double draw: 7H
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": f"dm-double-{suffix}",
                    "chat_type": "single",
                    "actor_telegram_id": f"tg-double-{suffix}",
                    "bet": 100,
                },
            )

        assert start_resp.status == 200
        start_data = await start_resp.json()
        assert start_data["success"] is True
        turn_version = start_data["data"]["turn_version"]

        double_resp = await self.client.request(
            "POST",
            "/bot/sessions/action",
            json={
                "chat_id": f"dm-double-{suffix}",
                "chat_type": "single",
                "actor_telegram_id": f"tg-double-{suffix}",
                "action": "double",
                "turn_version": turn_version,
            },
        )

        assert double_resp.status == 422
        double_data = await double_resp.json()
        assert double_data["success"] is False
        assert double_data["error"]["code"] == "game_logic_error"

    async def test_single_insurance_rejected_when_bank_cannot_cover_bet_and_insurance(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-ins-funds-{suffix}"
        chat_id = f"dm-ins-funds-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 100},
        )
        assert player_resp.status == 201

        # Dealer shows Ace so insurance appears in available moves.
        cards = iter(["10H", "7D", "AS", "9C"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )

        assert start_resp.status == 200
        start_data = await start_resp.json()
        assert start_data["success"] is True
        assert "insurance" not in start_data["data"]["available_moves"]

        insurance_resp = await self.client.request(
            "POST",
            "/bot/sessions/action",
            json={
                "chat_id": chat_id,
                "chat_type": "single",
                "actor_telegram_id": telegram_id,
                "action": "insurance",
                "turn_version": start_data["data"]["turn_version"],
                "hand_index": 0,
            },
        )

        assert insurance_resp.status == 422
        insurance_data = await insurance_resp.json()
        assert insurance_data["success"] is False
        assert insurance_data["error"]["code"] == "game_logic_error"

        async with db.engine.connect() as conn:
            bank_row = await conn.execute(
                text("SELECT bank FROM players WHERE telegram_id = :tg"),
                {"tg": telegram_id},
            )
            persisted_bank = bank_row.scalar_one()
            assert persisted_bank == 100

    async def test_single_double_valid_loss_updates_bank_by_2x_bet(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-double-loss-{suffix}"
        chat_id = f"dm-double-loss-{suffix}"

        initial_bank = 300
        initial_bet = 100

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": initial_bank},
        )
        assert player_resp.status == 201

        # Force deterministic loss after double:
        # P1: 10H,6D (16)
        # Dealer: 10S,QH (20) -> stands
        # Double draw: 2C -> P1 ends at 18 -> loses, bet becomes 200.
        cards = iter(["10H", "6D", "10S", "QH", "2C"])
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": initial_bet,
                },
            )

            assert start_resp.status == 200
            start_data = await start_resp.json()
            assert start_data["success"] is True
            turn_version = start_data["data"]["turn_version"]

            action_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "action": "double",
                    "turn_version": turn_version,
                },
            )
            assert action_resp.status == 200
            action_data = await action_resp.json()
            assert action_data["success"] is True
            assert action_data["data"]["session_status"] == "closed"

        participant = action_data["data"]["participants"][0]
        assert participant["participant_status"] == "settled"
        assert participant["result"] == "lose"
        assert participant["bet"] == initial_bet * 2
        assert participant["bank"] == initial_bank - (initial_bet * 2)
        assert participant["bank"] >= 0
        assert participant["delta"] == -(initial_bet * 2)

        last_resp = await self.client.request(
            "GET",
            f"/bot/sessions/last?chat_id={chat_id}&chat_type=single",
        )
        assert last_resp.status == 200
        last_data = await last_resp.json()
        assert last_data["success"] is True
        assert last_data["data"]["session_status"] == "closed"
        last_participant = last_data["data"]["participants"][0]
        assert last_participant["bank"] == initial_bank - (initial_bet * 2)

        async with db.engine.connect() as conn:
            bank_row = await conn.execute(
                text("SELECT bank FROM players WHERE telegram_id = :tg"),
                {"tg": telegram_id},
            )
            persisted_bank = bank_row.scalar_one()
            assert persisted_bank == initial_bank - (initial_bet * 2)

    async def test_single_session_settlement_never_makes_bank_negative(self):
        suffix = uuid4().hex[:8]

        telegram_id = f"tg-nonneg-{suffix}"
        chat_id = f"dm-nonneg-{suffix}"

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": telegram_id, "bank": 100},
        )
        assert player_resp.status == 201

        # Force a deterministic loss: player 16 vs dealer 20.
        cards = iter(["10H", "6D", "10S", "QH"])  # P1: 10H,6D; Dealer: 10S,QH
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/single/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "single",
                    "actor_telegram_id": telegram_id,
                    "bet": 100,
                },
            )

        assert start_resp.status == 200
        start_data = await start_resp.json()
        assert start_data["success"] is True
        turn_version = start_data["data"]["turn_version"]

        action_resp = await self.client.request(
            "POST",
            "/bot/sessions/action",
            json={
                "chat_id": chat_id,
                "chat_type": "single",
                "actor_telegram_id": telegram_id,
                "action": "stand",
                "turn_version": turn_version,
            },
        )

        assert action_resp.status == 200
        action_data = await action_resp.json()
        assert action_data["success"] is True
        assert action_data["data"]["session_status"] == "closed"
        assert action_data["data"]["participants"][0]["bank"] >= 0

        last_resp = await self.client.request(
            "GET",
            f"/bot/sessions/last?chat_id={chat_id}&chat_type=single",
        )
        assert last_resp.status == 200
        last_data = await last_resp.json()
        assert last_data["success"] is True
        assert last_data["data"]["session_status"] == "closed"
        assert last_data["data"]["participants"][0]["bank"] >= 0

        async with db.engine.connect() as conn:
            bank_row = await conn.execute(
                text("SELECT bank FROM players WHERE telegram_id = :tg"),
                {"tg": telegram_id},
            )
            persisted_bank = bank_row.scalar_one()
            assert persisted_bank >= 0

    async def test_group_session_settlement_never_makes_bank_negative(self):
        suffix = uuid4().hex[:8]

        admin_tg = f"tg-admin-nonneg-{suffix}"
        player_tg = f"tg-player-nonneg-{suffix}"
        chat_id = f"chat-nonneg-{suffix}"

        admin_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": admin_tg, "bank": 100},
        )
        assert admin_resp.status == 201

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": player_tg, "bank": 100},
        )
        assert player_resp.status == 201

        open_resp = await self.client.request(
            "POST",
            "/bot/sessions/group/open",
            json={
                "chat_id": chat_id,
                "chat_type": "group",
                "actor_telegram_id": admin_tg,
                "actor_is_admin": True,
                "bet": 100,
                "count_players": 2,
            },
        )
        assert open_resp.status == 201

        join_resp = await self.client.request(
            "POST",
            "/bot/sessions/group/join",
            json={
                "chat_id": chat_id,
                "chat_type": "group",
                "actor_telegram_id": player_tg,
                "bet": 100,
            },
        )
        assert join_resp.status == 200

        # Force deterministic losses for both players, dealer stands on 20.
        cards = iter(["10H", "6D", "9S", "7D", "10C", "QH"])  # P1, P2, Dealer
        with patch("app.services.blackjack_service.draw_card", side_effect=lambda: next(cards)):
            start_resp = await self.client.request(
                "POST",
                "/bot/sessions/group/start",
                json={
                    "chat_id": chat_id,
                    "chat_type": "group",
                    "actor_telegram_id": admin_tg,
                    "actor_is_admin": True,
                },
            )

        assert start_resp.status == 200
        data = await start_resp.json()
        assert data["success"] is True

        # Apply stand for each current player until session closes.
        for _ in range(4):
            if data["data"]["session_status"] == "closed":
                break
            current = data["data"]["current_player"]
            assert current is not None
            actor_telegram_id = current["telegram_id"]
            turn_version = data["data"]["turn_version"]

            action_resp = await self.client.request(
                "POST",
                "/bot/sessions/action",
                json={
                    "chat_id": chat_id,
                    "chat_type": "group",
                    "actor_telegram_id": actor_telegram_id,
                    "action": "stand",
                    "turn_version": turn_version,
                },
            )
            assert action_resp.status == 200
            data = await action_resp.json()
            assert data["success"] is True

        assert data["data"]["session_status"] == "closed"
        for participant in data["data"]["participants"]:
            assert participant["bank"] >= 0

        async with db.engine.connect() as conn:
            rows = await conn.execute(
                text("SELECT telegram_id, bank FROM players WHERE telegram_id IN (:a, :b)"),
                {"a": admin_tg, "b": player_tg},
            )
            persisted = {row[0]: row[1] for row in rows.all()}
            assert persisted[admin_tg] >= 0
            assert persisted[player_tg] >= 0
