"""Blackjack HTTP views based on aiohttp class-based view API."""
from __future__ import annotations

from aiohttp import web

from app.accessors import blackjack_accessor_key, bot_accessor_key, catalog_accessor_key
from app.api.base_view import BaseView
from app.api.docs import swagger_doc
from app.core.config import settings
from app.errors import parse_json_or_bad_request
from app.schemas import (
    ActionRequest,
    AdminBanRequest,
    AdminBanResponse,
    AdminTopupRequest,
    AdminTopupResponse,
    BotActionRequest,
    BotSessionQueryRequest,
    BotTimeoutRequest,
    DeckCreateRequest,
    DeckCreateResponse,
    GroupLobbyJoinRequest,
    GroupLobbyOpenRequest,
    GroupLobbyQueryRequest,
    GroupLobbyStartRequest,
    GroupPlayerStopRequest,
    GroupSessionSnapshotCanonicalResponse,
    GroupSessionSnapshotResponse,
    PlayerCreateRequest,
    PlayerCreateResponse,
    SeatCreateRequest,
    SeatCreateResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStateResponse,
    SingleSessionStopRequest,
    SingleSessionStartRequest,
    TimeoutRequest,
)


BOT_SNAPSHOT_RESPONSE_MODEL = (
    GroupSessionSnapshotResponse
    if settings.bot_snapshot_include_legacy_fields
    else GroupSessionSnapshotCanonicalResponse
)


class PlayersView(BaseView):
    @swagger_doc(
        summary="Create player",
        description="Creates a player profile with initial bank.",
        tags=["catalog"],
        request_model=PlayerCreateRequest,
        response_model=PlayerCreateResponse,
        success_status=201,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(PlayerCreateRequest)
        accessor = self.request.app[catalog_accessor_key]
        data = await accessor.create_player(payload)
        return self.success_response(data, status=201)


class DecksView(BaseView):
    @swagger_doc(
        summary="Create deck",
        description="Creates a logical deck for a chat/game room.",
        tags=["catalog"],
        request_model=DeckCreateRequest,
        response_model=DeckCreateResponse,
        success_status=201,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(DeckCreateRequest)
        accessor = self.request.app[catalog_accessor_key]
        data = await accessor.create_deck(payload)
        return self.success_response(data, status=201)


class SessionsView(BaseView):
    @swagger_doc(
        summary="Create session",
        description="Creates a blackjack session bound to a deck.",
        tags=["catalog"],
        request_model=SessionCreateRequest,
        response_model=SessionCreateResponse,
        success_status=201,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(SessionCreateRequest)
        accessor = self.request.app[catalog_accessor_key]
        data = await accessor.create_session(payload)
        return self.success_response(data, status=201)


class SessionPlayersView(BaseView):
    @swagger_doc(
        summary="Seat player",
        description="Adds a player to a session at a table position with bet.",
        tags=["catalog"],
        request_model=SeatCreateRequest,
        response_model=SeatCreateResponse,
        success_status=201,
    )
    async def put(self) -> web.Response:
        session_id = self.parse_session_id()
        payload = await self.parse_json(SeatCreateRequest)
        accessor = self.request.app[catalog_accessor_key]
        data = await accessor.seat_player(session_id, payload)
        return self.success_response(data, status=201)


class SessionStartView(BaseView):
    @swagger_doc(
        summary="Start blackjack session",
        description="Deals initial hands and activates first turn.",
        tags=["blackjack"],
        response_model=SessionStateResponse,
    )
    async def put(self) -> web.Response:
        session_id = self.parse_session_id()
        accessor = self.request.app[blackjack_accessor_key]
        data = await accessor.start_session(session_id)
        return self.success_response(data)


class SessionActionsView(BaseView):
    @swagger_doc(
        summary="Apply player action",
        description="Applies hit/stand/double for the active player.",
        tags=["blackjack"],
        request_model=ActionRequest,
        response_model=SessionStateResponse,
    )
    async def put(self) -> web.Response:
        session_id = self.parse_session_id()
        payload = await self.parse_json(ActionRequest)
        accessor = self.request.app[blackjack_accessor_key]
        data = await accessor.make_action(session_id, payload)
        return self.success_response(data)


class SessionTimeoutView(BaseView):
    @swagger_doc(
        summary="Force timeout",
        description="Forces timeout handling for current or given position.",
        tags=["blackjack"],
        request_model=TimeoutRequest,
        response_model=SessionStateResponse,
    )
    async def put(self) -> web.Response:
        session_id = self.parse_session_id()
        payload = await self.parse_json(TimeoutRequest)
        accessor = self.request.app[blackjack_accessor_key]
        data = await accessor.force_timeout(session_id, payload)
        return self.success_response(data)


class SessionStateView(BaseView):
    @swagger_doc(
        summary="Get session state",
        description="Returns current blackjack session snapshot.",
        tags=["blackjack"],
        response_model=SessionStateResponse,
    )
    async def get(self) -> web.Response:
        session_id = self.parse_session_id()
        accessor = self.request.app[blackjack_accessor_key]
        data = await accessor.get_session_state(session_id)
        return self.success_response(data)


class GroupLobbyOpenView(BaseView):
    @swagger_doc(
        summary="Open group lobby",
        description="Creates a group lobby by chat_id and auto-joins the admin actor.",
        tags=["bot"],
        request_model=GroupLobbyOpenRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
        success_status=201,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(GroupLobbyOpenRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.open_group_lobby(payload)
        return self.success_response(data, status=201)


class GroupLobbyJoinView(BaseView):
    @swagger_doc(
        summary="Join group lobby",
        description="Registers a player in the current group lobby by chat_id.",
        tags=["bot"],
        request_model=GroupLobbyJoinRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(GroupLobbyJoinRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.join_group_lobby(payload)
        return self.success_response(data)


class GroupLobbyStateView(BaseView):
    @swagger_doc(
        summary="Get group lobby",
        description="Returns the current lobby snapshot for a group chat.",
        tags=["bot"],
        query_model=GroupLobbyQueryRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
    )
    async def get(self) -> web.Response:
        payload = parse_json_or_bad_request(dict(self.request.query), GroupLobbyQueryRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.get_group_lobby(payload)
        return self.success_response(data)


class GroupLobbyStartView(BaseView):
    @swagger_doc(
        summary="Start group lobby",
        description="Starts a group blackjack round by chat_id.",
        tags=["bot"],
        request_model=GroupLobbyStartRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(GroupLobbyStartRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.start_group_lobby(payload)
        return self.success_response(data)


class SingleSessionStartView(BaseView):
    @swagger_doc(
        summary="Start single session",
        description="Creates and immediately starts a single-player blackjack session by chat_id.",
        tags=["bot"],
        request_model=SingleSessionStartRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(SingleSessionStartRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.start_single_session(payload)
        return self.success_response(data)


class GroupPlayerStopView(BaseView):
    @swagger_doc(
        summary="Stop group player",
        description="Settles the current player hand and removes that participant from active group play.",
        tags=["bot"],
        request_model=GroupPlayerStopRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(GroupPlayerStopRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.stop_group_player(payload)
        return self.success_response(data)


class SingleSessionStopView(BaseView):
    @swagger_doc(
        summary="Stop single session",
        description="Settles the current single-player table and closes the session.",
        tags=["bot"],
        request_model=SingleSessionStopRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(SingleSessionStopRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.stop_single_session(payload)
        return self.success_response(data)


class BotCurrentSessionView(BaseView):
    @swagger_doc(
        summary="Get current bot session",
        description="Returns the current unfinished bot-facing session snapshot by chat_id and chat_type.",
        tags=["bot"],
        query_model=BotSessionQueryRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
    )
    async def get(self) -> web.Response:
        payload = parse_json_or_bad_request(dict(self.request.query), BotSessionQueryRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.get_current_session(payload)
        return self.success_response(data)


class BotLastSessionView(BaseView):
    @swagger_doc(
        summary="Get last bot session",
        description="Returns the last closed bot-facing session snapshot by chat_id and chat_type.",
        tags=["bot"],
        query_model=BotSessionQueryRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
    )
    async def get(self) -> web.Response:
        payload = parse_json_or_bad_request(dict(self.request.query), BotSessionQueryRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.get_last_session(payload)
        return self.success_response(data)


class BotActionView(BaseView):
    @swagger_doc(
        summary="Apply bot action",
        description="Applies a blackjack action by chat_id for the current active participant.",
        tags=["bot"],
        request_model=BotActionRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(BotActionRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.apply_action(payload)
        return self.success_response(data)


class BotTimeoutView(BaseView):
    @swagger_doc(
        summary="Apply bot timeout",
        description="Applies timeout for the current active turn by chat_id.",
        tags=["bot"],
        request_model=BotTimeoutRequest,
        response_model=BOT_SNAPSHOT_RESPONSE_MODEL,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(BotTimeoutRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.apply_timeout(payload)
        return self.success_response(data)


class AdminTopupView(BaseView):
    @swagger_doc(
        summary="Admin topup",
        description="Adds amount to a player's bank by username. Admin-only.",
        tags=["admin"],
        request_model=AdminTopupRequest,
        response_model=AdminTopupResponse,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(AdminTopupRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.admin_topup(payload)
        return self.success_response(data)


class AdminBanView(BaseView):
    @swagger_doc(
        summary="Admin ban",
        description="Bans a player by username. Banned players cannot start or join sessions.",
        tags=["admin"],
        request_model=AdminBanRequest,
        response_model=AdminBanResponse,
    )
    async def post(self) -> web.Response:
        payload = await self.parse_json(AdminBanRequest)
        accessor = self.request.app[bot_accessor_key]
        data = await accessor.admin_ban(payload)
        return self.success_response(data)


def setup_blackjack_routes(app: web.Application) -> None:
    app.router.add_routes([web.view(path, view) for path, view in BLACKJACK_VIEW_ROUTES])


BLACKJACK_VIEW_ROUTES: list[tuple[str, type[web.View]]] = [
    ("/players", PlayersView),
    ("/decks", DecksView),
    ("/sessions", SessionsView),
    ("/sessions/{session_id}/players", SessionPlayersView),
    ("/sessions/{session_id}/start", SessionStartView),
    ("/sessions/{session_id}/actions", SessionActionsView),
    ("/sessions/{session_id}/timeout", SessionTimeoutView),
    ("/sessions/{session_id}", SessionStateView),
    ("/bot/sessions/group/open", GroupLobbyOpenView),
    ("/bot/sessions/group/join", GroupLobbyJoinView),
    ("/bot/sessions/group/lobby", GroupLobbyStateView),
    ("/bot/sessions/group/start", GroupLobbyStartView),
    ("/bot/sessions/group/player-stop", GroupPlayerStopView),
    ("/bot/sessions/single/start", SingleSessionStartView),
    ("/bot/sessions/single/stop", SingleSessionStopView),
    ("/bot/sessions/current", BotCurrentSessionView),
    ("/bot/sessions/last", BotLastSessionView),
    ("/bot/sessions/action", BotActionView),
    ("/bot/sessions/timeout", BotTimeoutView),
    ("/admin/topup", AdminTopupView),
    ("/admin/ban", AdminBanView),
]
