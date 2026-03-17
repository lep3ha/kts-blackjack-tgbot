from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from app.api.middlewares import error_middleware
from app.errors import BadRequestError, GameLogicError, StateTransitionError


class TestErrorMiddleware(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        app = web.Application(middlewares=[error_middleware])

        async def bad_request(_request):
            raise BadRequestError("invalid payload")

        async def game_logic(_request):
            raise GameLogicError("illegal move")

        async def unknown_error(_request):
            raise RuntimeError("boom")

        async def state_transition(_request):
            raise StateTransitionError("Event 'x' is not allowed")

        app.router.add_get("/bad", bad_request)
        app.router.add_get("/logic", game_logic)
        app.router.add_get("/unknown", unknown_error)
        app.router.add_get("/transition", state_transition)
        return app

    async def test_bad_request(self):
        resp = await self.client.request("GET", "/bad")
        data = await resp.json()
        assert resp.status == 400
        assert data["success"] is False
        assert data["error"]["code"] == "bad_request"

    async def test_game_logic_error(self):
        resp = await self.client.request("GET", "/logic")
        data = await resp.json()
        assert resp.status == 422
        assert data["success"] is False
        assert data["error"]["code"] == "game_logic_error"

    async def test_internal_error(self):
        resp = await self.client.request("GET", "/unknown")
        data = await resp.json()
        assert resp.status == 500
        assert data["success"] is False
        assert data["error"]["code"] == "internal_error"

    async def test_state_transition_error(self):
        resp = await self.client.request("GET", "/transition")
        data = await resp.json()
        assert resp.status == 409
        assert data["success"] is False
        assert data["error"]["code"] == "state_conflict"
