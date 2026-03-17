"""Tests for Admin API endpoints: /admin/topup and /admin/ban."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from app.accessors import bot_accessor_key
from app.api.views import setup_blackjack_routes
from app.api.middlewares import error_middleware
from app.errors import NotFoundError


class TestAdminApi(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        from app.accessors import blackjack_accessor_key, catalog_accessor_key

        app = web.Application(middlewares=[error_middleware])
        self.bot_accessor = SimpleNamespace(
            admin_topup=AsyncMock(),
            admin_ban=AsyncMock(),
            # stubs for other routes registered by setup_blackjack_routes
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
        )
        app[catalog_accessor_key] = SimpleNamespace(
            create_player=AsyncMock(),
            create_deck=AsyncMock(),
            create_session=AsyncMock(),
            seat_player=AsyncMock(),
        )
        app[blackjack_accessor_key] = SimpleNamespace(
            start_session=AsyncMock(),
            make_action=AsyncMock(),
            force_timeout=AsyncMock(),
            get_session_state=AsyncMock(),
        )
        app[bot_accessor_key] = self.bot_accessor
        setup_blackjack_routes(app)
        return app

    # ------------------------------------------------------------------
    # /admin/topup
    # ------------------------------------------------------------------

    async def test_topup_happy_path(self):
        self.bot_accessor.admin_topup.return_value = {"username": "alice", "new_bank": 1500}
        resp = await self.client.request(
            "POST", "/admin/topup", json={"username": "alice", "amount": 500}
        )
        data = await resp.json()
        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["username"] == "alice"
        assert data["data"]["new_bank"] == 1500

    async def test_topup_player_not_found(self):
        self.bot_accessor.admin_topup.side_effect = NotFoundError("Player with username 'ghost' not found")
        resp = await self.client.request(
            "POST", "/admin/topup", json={"username": "ghost", "amount": 100}
        )
        data = await resp.json()
        assert resp.status == 404
        assert data["success"] is False
        assert data["error"]["code"] == "not_found"

    async def test_topup_invalid_amount_zero(self):
        resp = await self.client.request(
            "POST", "/admin/topup", json={"username": "alice", "amount": 0}
        )
        data = await resp.json()
        assert resp.status == 400
        assert data["success"] is False

    async def test_topup_invalid_amount_negative(self):
        resp = await self.client.request(
            "POST", "/admin/topup", json={"username": "alice", "amount": -100}
        )
        data = await resp.json()
        assert resp.status == 400
        assert data["success"] is False

    async def test_topup_missing_username(self):
        resp = await self.client.request(
            "POST", "/admin/topup", json={"amount": 100}
        )
        assert resp.status == 400

    async def test_topup_missing_amount(self):
        resp = await self.client.request(
            "POST", "/admin/topup", json={"username": "alice"}
        )
        assert resp.status == 400

    # ------------------------------------------------------------------
    # /admin/ban
    # ------------------------------------------------------------------

    async def test_ban_happy_path(self):
        self.bot_accessor.admin_ban.return_value = {"username": "badguy", "is_banned": True}
        resp = await self.client.request(
            "POST", "/admin/ban", json={"username": "badguy"}
        )
        data = await resp.json()
        assert resp.status == 200
        assert data["success"] is True
        assert data["data"]["is_banned"] is True

    async def test_ban_player_not_found(self):
        self.bot_accessor.admin_ban.side_effect = NotFoundError("Player with username 'ghost' not found")
        resp = await self.client.request(
            "POST", "/admin/ban", json={"username": "ghost"}
        )
        data = await resp.json()
        assert resp.status == 404
        assert data["error"]["code"] == "not_found"

    async def test_ban_missing_username(self):
        resp = await self.client.request("POST", "/admin/ban", json={})
        assert resp.status == 400

    # ------------------------------------------------------------------
    # Ban enforcement: accessor raises AuthorizationError when is_banned=True
    # (tested via mocked accessor — the enforcement logic is in bot_accessor.py)
    # ------------------------------------------------------------------

    async def test_single_start_blocked_when_banned(self):
        from app.errors import AuthorizationError

        self.bot_accessor.start_single_session.side_effect = AuthorizationError("Player is banned")
        resp = await self.client.request(
            "POST",
            "/bot/sessions/single/start",
            json={
                "chat_id": "42",
                "chat_type": "single",
                "actor_telegram_id": "7",
                "bet": 100,
            },
        )
        data = await resp.json()
        assert resp.status == 403
        assert data["error"]["code"] == "authorization_error"

    async def test_group_open_blocked_when_banned(self):
        from app.errors import AuthorizationError

        self.bot_accessor.open_group_lobby.side_effect = AuthorizationError("Player is banned")
        resp = await self.client.request(
            "POST",
            "/bot/sessions/group/open",
            json={
                "chat_id": "100",
                "chat_type": "group",
                "actor_telegram_id": "7",
                "actor_is_admin": True,
                "bet": 100,
            },
        )
        data = await resp.json()
        assert resp.status == 403
        assert data["error"]["code"] == "authorization_error"

    async def test_group_join_blocked_when_banned(self):
        from app.errors import AuthorizationError

        self.bot_accessor.join_group_lobby.side_effect = AuthorizationError("Player is banned")
        resp = await self.client.request(
            "POST",
            "/bot/sessions/group/join",
            json={
                "chat_id": "100",
                "chat_type": "group",
                "actor_telegram_id": "7",
                "bet": 100,
            },
        )
        data = await resp.json()
        assert resp.status == 403
        assert data["error"]["code"] == "authorization_error"
