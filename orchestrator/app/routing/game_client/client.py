import logging
from typing import Any

import aiohttp

from app.routing.game_client.interfaces import GameServiceClient
from app.routing.game_client.models import (
    AdminBanRequest,
    AdminTopupRequest,
    CurrentSessionRequest,
    GameErrorCode,
    GameServiceEnvelope,
    GroupJoinRequest,
    GroupOpenRequest,
    GroupPlayerStopRequest,
    GroupStartRequest,
    PlayerActionRequest,
    PlayerBalanceRequest,
    RegisterPlayerRequest,
    SingleStartRequest,
    SingleStopRequest,
    TimeoutTurnRequest,
)


logger = logging.getLogger(__name__)


class GameServiceTransportError(RuntimeError):
    """Raised when game-service is unreachable or returns invalid transport data."""


class HttpGameServiceClient(GameServiceClient):
    def __init__(
        self,
        *,
        base_url: str,
        request_timeout_seconds: float,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session
        self._owns_session = session is None
        self._timeout = aiohttp.ClientTimeout(total=request_timeout_seconds)

    async def __aenter__(self) -> "HttpGameServiceClient":
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def group_open(self, request: GroupOpenRequest) -> GameServiceEnvelope:
        return await self._post("/bot/sessions/group/open", request.model_dump())

    async def group_start(self, request: GroupStartRequest) -> GameServiceEnvelope:
        return await self._post("/bot/sessions/group/start", request.model_dump())

    async def group_join(self, request: GroupJoinRequest) -> GameServiceEnvelope:
        return await self._post("/bot/sessions/group/join", request.model_dump())

    async def group_player_stop(self, request: GroupPlayerStopRequest) -> GameServiceEnvelope:
        return await self._post("/bot/sessions/group/player-stop", request.model_dump())

    async def single_start(self, request: SingleStartRequest) -> GameServiceEnvelope:
        return await self._post("/bot/sessions/single/start", request.model_dump())

    async def single_stop(self, request: SingleStopRequest) -> GameServiceEnvelope:
        return await self._post("/bot/sessions/single/stop", request.model_dump())

    async def register_player(self, request: RegisterPlayerRequest) -> GameServiceEnvelope:
        return await self._post("/players", request.model_dump())

    async def player_balance(self, request: PlayerBalanceRequest) -> GameServiceEnvelope:
        return await self._get(f"/players/telegram/{request.telegram_id}", params={})

    async def player_action(self, request: PlayerActionRequest) -> GameServiceEnvelope:
        return await self._post("/bot/sessions/action", request.model_dump())

    async def timeout_turn(self, request: TimeoutTurnRequest) -> GameServiceEnvelope:
        return await self._post("/bot/sessions/timeout", request.model_dump())

    async def current_session(self, request: CurrentSessionRequest) -> GameServiceEnvelope:
        params = request.model_dump()
        return await self._get("/bot/sessions/current", params=params)

    async def admin_topup(self, request: AdminTopupRequest) -> GameServiceEnvelope:
        return await self._post("/admin/topup", request.model_dump())

    async def admin_ban(self, request: AdminBanRequest) -> GameServiceEnvelope:
        return await self._post("/admin/ban", request.model_dump())

    async def _post(self, path: str, payload: dict[str, Any]) -> GameServiceEnvelope:
        session = self._require_session()
        url = f"{self._base_url}{path}"
        try:
            async with session.post(url, json=payload) as response:
                body = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise GameServiceTransportError(f"POST {url} failed") from exc

        return self._parse_envelope(url=url, body=body)

    async def _get(self, path: str, params: dict[str, Any]) -> GameServiceEnvelope:
        session = self._require_session()
        url = f"{self._base_url}{path}"
        try:
            async with session.get(url, params=params) as response:
                body = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise GameServiceTransportError(f"GET {url} failed") from exc

        return self._parse_envelope(url=url, body=body)

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is not None:
            return self._session

        self._session = aiohttp.ClientSession(timeout=self._timeout)
        self._owns_session = True
        return self._session

    @staticmethod
    def _parse_envelope(*, url: str, body: Any) -> GameServiceEnvelope:
        if not isinstance(body, dict):
            raise GameServiceTransportError(f"{url} returned non-object payload")

        parsed = dict(body)
        error = parsed.get("error")
        if isinstance(error, dict):
            parsed["error"] = {
                **error,
                "code": HttpGameServiceClient._map_error_code(error.get("code")),
            }

        try:
            return GameServiceEnvelope.model_validate(parsed)
        except Exception as exc:
            raise GameServiceTransportError(f"{url} returned invalid envelope") from exc

    @staticmethod
    def _map_error_code(raw_code: Any) -> str:
        if not isinstance(raw_code, str):
            return GameErrorCode.UNKNOWN.value

        valid_codes = {code.value for code in GameErrorCode}
        if raw_code not in valid_codes:
            return GameErrorCode.UNKNOWN.value

        return raw_code