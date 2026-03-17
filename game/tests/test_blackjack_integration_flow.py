import unittest
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from sqlalchemy import text

from app.core.datetime_utils import utc_now_naive
from app.db import db
from app.main import init_app


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

        last_resp = await self.client.request(
            "GET",
            f"/bot/sessions/last?chat_id=dm-stop-{suffix}&chat_type=single",
        )
        assert last_resp.status == 200
        last_data = await last_resp.json()
        assert last_data["success"] is True
        assert last_data["data"]["session_status"] == "closed"
        assert last_data["data"]["participants"][0]["result"] == "win"

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

    async def test_single_action_stale_turn_rejected(self):
        suffix = uuid4().hex[:8]

        player_resp = await self.client.request(
            "POST",
            "/players",
            json={"telegram_id": f"tg-stale-{suffix}", "bank": 1000},
        )
        assert player_resp.status == 201

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
