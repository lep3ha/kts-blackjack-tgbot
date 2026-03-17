from aiohttp.test_utils import AioHTTPTestCase

from app.main import init_app


class TestHealthCheck(AioHTTPTestCase):
    async def get_application(self):
        return await init_app()

    async def test_health_check(self):
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "ok"
