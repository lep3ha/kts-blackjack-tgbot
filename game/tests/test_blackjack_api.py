from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from app.accessors import blackjack_accessor_key, catalog_accessor_key
from app.accessors import bot_accessor_key
from app.api.views import setup_blackjack_routes
from app.api.middlewares import error_middleware


class TestBlackjackApi(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        app = web.Application(middlewares=[error_middleware])

        self.catalog_accessor = SimpleNamespace(
            create_player=AsyncMock(),
            create_deck=AsyncMock(),
            create_session=AsyncMock(),
            seat_player=AsyncMock(),
        )
        self.blackjack_accessor = SimpleNamespace(
            start_session=AsyncMock(),
            make_action=AsyncMock(),
            force_timeout=AsyncMock(),
            get_session_state=AsyncMock(),
        )
        self.bot_accessor = SimpleNamespace(
            apply_action=AsyncMock(),
            apply_timeout=AsyncMock(),
            get_current_session=AsyncMock(),
            get_last_session=AsyncMock(),
            open_group_lobby=AsyncMock(),
            join_group_lobby=AsyncMock(),
            get_group_lobby=AsyncMock(),
            start_group_lobby=AsyncMock(),
            stop_group_player=AsyncMock(),
            start_single_session=AsyncMock(),
            stop_single_session=AsyncMock(),
                admin_topup=AsyncMock(),
                admin_ban=AsyncMock(),
        )

        app[catalog_accessor_key] = self.catalog_accessor
        app[blackjack_accessor_key] = self.blackjack_accessor
        app[bot_accessor_key] = self.bot_accessor
        setup_blackjack_routes(app)
        return app

    async def test_start_with_invalid_session_id(self):
        resp = await self.client.request("PUT", "/sessions/not-an-int/start")
        data = await resp.json()
        assert resp.status == 400
        assert data["success"] is False
        assert data["error"]["code"] == "bad_request"

    async def test_action_with_invalid_payload(self):
        payload = {"position": 1, "action": "split"}
        resp = await self.client.request("PUT", "/sessions/1/actions", json=payload)
        data = await resp.json()
        assert resp.status == 400
        assert data["success"] is False
        assert data["error"]["code"] == "bad_request"

    async def test_action_happy_path(self):
        self.blackjack_accessor.make_action.return_value = {
            "session_id": 1,
            "deck_id": 10,
            "status": "in_progress",
            "state": "player_turn",
            "available_moves": ["hit", "stand"],
            "current_position": 2,
            "current_timer": None,
            "dealer_cards": ["9H"],
            "players": [
                {
                    "player_id": 100,
                    "position": 1,
                    "bet": 50,
                    "cards": ["AS", "KD"],
                    "bank": 950,
                }
            ],
        }

        payload = {"position": 1, "action": "stand"}
        resp = await self.client.request("PUT", "/sessions/1/actions", json=payload)

        data = await resp.json()
        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["session_id"] == 1
        assert data["data"]["status"] == "in_progress"
        assert data["data"]["available_moves"] == ["hit", "stand"]
        assert data["data"]["players"][0]["player_id"] == 100
        self.blackjack_accessor.make_action.assert_awaited_once()

    async def test_group_open_happy_path(self):
        self.bot_accessor.open_group_lobby.return_value = {
            "chat_id": "chat-1",
            "chat_mode": "group",
            "session_id": 10,
            "session_status": "lobby_open",
            "runtime_state": "waiting",
            "available_moves": [],
            "current_position": None,
            "current_timer": None,
            "dealer": {"cards": [], "is_final": False},
            "participants": [
                {
                    "telegram_id": "tg-admin",
                    "player_id": 1,
                    "position": 1,
                    "participant_status": "joined",
                    "bet": 100,
                    "cards": [],
                    "bank": 1000,
                }
            ],
            "can_start": True,
            "start_error": None,
        }

        resp = await self.client.request(
            "POST",
            "/bot/sessions/group/open",
            json={
                "chat_id": "chat-1",
                "chat_type": "group",
                "actor_telegram_id": "tg-admin",
                "actor_is_admin": True,
                "bet": 100,
            },
        )

        data = await resp.json()
        assert resp.status == 201
        assert data["success"] is True
        assert data["data"]["session_status"] == "lobby_open"
        assert data["data"]["participants"][0]["telegram_id"] == "tg-admin"
        self.bot_accessor.open_group_lobby.assert_awaited_once()

    async def test_group_lobby_requires_chat_id_query(self):
        resp = await self.client.request("GET", "/bot/sessions/group/lobby")
        data = await resp.json()

        assert resp.status == 400
        assert data["success"] is False
        assert data["error"]["code"] == "bad_request"

    async def test_group_start_happy_path(self):
        self.bot_accessor.start_group_lobby.return_value = {
            "chat_id": "chat-1",
            "chat_mode": "group",
            "session_id": 10,
            "session_status": "in_progress",
            "runtime_state": "player_turn",
            "available_moves": ["hit", "stand"],
            "current_position": 1,
            "current_timer": None,
            "dealer": {"cards": ["9H", "7S"], "is_final": False},
            "participants": [
                {
                    "telegram_id": "tg-admin",
                    "player_id": 1,
                    "position": 1,
                    "participant_status": "active",
                    "bet": 100,
                    "cards": ["AS", "KD"],
                    "bank": 1000,
                }
            ],
            "can_start": False,
            "start_error": "Session is not in lobby_open state",
        }

        resp = await self.client.request(
            "POST",
            "/bot/sessions/group/start",
            json={
                "chat_id": "chat-1",
                "chat_type": "group",
                "actor_telegram_id": "tg-admin",
                "actor_is_admin": True,
            },
        )

        data = await resp.json()
        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["session_status"] == "in_progress"
        assert data["data"]["available_moves"] == ["hit", "stand"]
        self.bot_accessor.start_group_lobby.assert_awaited_once()

    async def test_single_start_happy_path(self):
        self.bot_accessor.start_single_session.return_value = {
            "chat_id": "dm-1",
            "chat_mode": "single",
            "session_id": 20,
            "session_status": "in_progress",
            "runtime_state": "player_turn",
            "available_moves": ["hit", "stand", "double"],
            "current_position": 1,
            "current_timer": None,
            "dealer": {"cards": ["9H", "7S"], "is_final": False},
            "participants": [
                {
                    "telegram_id": "tg-user",
                    "player_id": 2,
                    "position": 1,
                    "participant_status": "active",
                    "bet": 100,
                    "cards": ["AS", "KD"],
                    "bank": 1000,
                }
            ],
            "can_start": False,
            "start_error": "Session is not in lobby_open state",
        }

        resp = await self.client.request(
            "POST",
            "/bot/sessions/single/start",
            json={
                "chat_id": "dm-1",
                "chat_type": "single",
                "actor_telegram_id": "tg-user",
                "bet": 100,
            },
        )

        data = await resp.json()
        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["chat_mode"] == "single"
        assert data["data"]["session_status"] == "in_progress"
        assert data["data"]["participants"][0]["participant_status"] == "active"
        self.bot_accessor.start_single_session.assert_awaited_once()

    async def test_group_player_stop_happy_path(self):
        self.bot_accessor.stop_group_player.return_value = {
            "chat_id": "chat-1",
            "chat_mode": "group",
            "session_id": 10,
            "session_status": "in_progress",
            "runtime_state": "player_turn",
            "available_moves": ["hit", "stand"],
            "current_position": 2,
            "current_timer": None,
            "dealer": {"cards": ["9H", "7S"], "is_final": False},
            "participants": [
                {
                    "telegram_id": "tg-a",
                    "player_id": 1,
                    "position": 1,
                    "participant_status": "inactive",
                    "bet": 100,
                    "cards": ["10H", "7D"],
                    "bank": 1100,
                    "result": "win",
                    "delta": 100,
                },
                {
                    "telegram_id": "tg-b",
                    "player_id": 2,
                    "position": 2,
                    "participant_status": "active",
                    "bet": 100,
                    "cards": ["8S", "8D"],
                    "bank": 1000,
                    "result": None,
                    "delta": None,
                },
            ],
            "can_start": False,
            "start_error": "Session is not in lobby_open state",
        }

        resp = await self.client.request(
            "POST",
            "/bot/sessions/group/player-stop",
            json={
                "chat_id": "chat-1",
                "chat_type": "group",
                "actor_telegram_id": "tg-a",
            },
        )

        data = await resp.json()
        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["participants"][0]["participant_status"] == "inactive"
        assert data["data"]["participants"][0]["result"] == "win"
        self.bot_accessor.stop_group_player.assert_awaited_once()

    async def test_single_stop_happy_path(self):
        self.bot_accessor.stop_single_session.return_value = {
            "chat_id": "dm-1",
            "chat_mode": "single",
            "session_id": 20,
            "session_status": "closed",
            "runtime_state": "closed",
            "turn_version": 0,
            "available_moves": [],
            "current_position": None,
            "current_timer": None,
            "dealer": {"cards": ["9H", "7S"], "is_final": True},
            "participants": [
                {
                    "telegram_id": "tg-user",
                    "player_id": 2,
                    "position": 1,
                    "participant_status": "settled",
                    "bet": 100,
                    "cards": ["10H", "7D"],
                    "bank": 1100,
                    "result": "win",
                    "delta": 100,
                }
            ],
            "can_start": False,
            "start_error": "Session is not in lobby_open state",
        }

        resp = await self.client.request(
            "POST",
            "/bot/sessions/single/stop",
            json={
                "chat_id": "dm-1",
                "chat_type": "single",
                "actor_telegram_id": "tg-user",
            },
        )

        data = await resp.json()
        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["session_status"] == "closed"
        assert data["data"]["participants"][0]["result"] == "win"
        self.bot_accessor.stop_single_session.assert_awaited_once()

    async def test_current_session_happy_path(self):
        self.bot_accessor.get_current_session.return_value = {
            "chat_id": "chat-1",
            "chat_mode": "group",
            "session_id": 10,
            "session_status": "in_progress",
            "runtime_state": "player_turn",
            "available_moves": ["hit", "stand"],
            "current_position": 2,
            "current_timer": None,
            "dealer": {"cards": ["9H"], "is_final": False},
            "participants": [],
            "can_start": False,
            "start_error": "Session is not in lobby_open state",
        }

        resp = await self.client.request("GET", "/bot/sessions/current?chat_id=chat-1&chat_type=group")
        data = await resp.json()

        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["session_id"] == 10
        self.bot_accessor.get_current_session.assert_awaited_once()

    async def test_last_session_happy_path(self):
        self.bot_accessor.get_last_session.return_value = {
            "chat_id": "dm-1",
            "chat_mode": "single",
            "session_id": 20,
            "session_status": "closed",
            "runtime_state": "closed",
            "turn_version": 0,
            "available_moves": [],
            "current_position": None,
            "current_timer": None,
            "dealer": {"cards": ["9H", "7S"], "is_final": True},
            "participants": [
                {
                    "telegram_id": "tg-user",
                    "player_id": 2,
                    "position": 1,
                    "participant_status": "settled",
                    "bet": 100,
                    "cards": ["10H", "7D"],
                    "bank": 1100,
                    "result": "win",
                    "delta": 100,
                }
            ],
            "can_start": False,
            "start_error": "Session is not in lobby_open state",
        }

        resp = await self.client.request("GET", "/bot/sessions/last?chat_id=dm-1&chat_type=single")
        data = await resp.json()

        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["session_status"] == "closed"
        assert data["data"]["participants"][0]["delta"] == 100
        self.bot_accessor.get_last_session.assert_awaited_once()

    async def test_bot_action_happy_path(self):
        self.bot_accessor.apply_action.return_value = {
            "chat_id": "dm-1",
            "chat_mode": "single",
            "session_id": 20,
            "session_status": "closed",
            "runtime_state": "closed",
            "available_moves": [],
            "current_position": None,
            "current_timer": None,
            "dealer": {"cards": ["9H", "7S", "5D"], "is_final": True},
                "current_player": None,
            "participants": [
                {
                    "telegram_id": "tg-user",
                    "player_id": 2,
                    "position": 1,
                    "participant_status": "settled",
                    "bet": 100,
                    "cards": ["10H", "7D"],
                    "bank": 1100,
                    "result": "win",
                    "delta": 100,
                }
            ],
            "can_start": False,
            "start_error": "Session is not in lobby_open state",
        }

        resp = await self.client.request(
            "POST",
            "/bot/sessions/action",
            json={
                "chat_id": "dm-1",
                "chat_type": "single",
                "actor_telegram_id": "tg-user",
                "action": "stand",
                "turn_version": 0,
            },
        )
        data = await resp.json()

        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["session_status"] == "closed"
        self.bot_accessor.apply_action.assert_awaited_once()

    async def test_bot_timeout_happy_path(self):
        self.bot_accessor.apply_timeout.return_value = {
            "chat_id": "dm-1",
            "chat_mode": "single",
            "session_id": 20,
            "session_status": "closed",
            "runtime_state": "closed",
            "available_moves": [],
            "current_position": None,
            "current_timer": None,
            "dealer": {"cards": ["9H", "7S", "5D"], "is_final": True},
                "current_player": None,
            "participants": [
                {
                    "telegram_id": "tg-user",
                    "player_id": 2,
                    "position": 1,
                    "participant_status": "settled",
                    "bet": 100,
                    "cards": ["10H", "7D"],
                    "bank": 1100,
                    "result": "win",
                    "delta": 100,
                }
            ],
            "can_start": False,
            "start_error": "Session is not in lobby_open state",
        }

        resp = await self.client.request(
            "POST",
            "/bot/sessions/timeout",
            json={
                "chat_id": "dm-1",
                "chat_type": "single",
                "turn_version": 0,
            },
        )
        data = await resp.json()

        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["session_status"] == "closed"
        self.bot_accessor.apply_timeout.assert_awaited_once()
