"""Bot-facing API views for group/single flows."""
from __future__ import annotations

from aiohttp import web

from app.accessors import bot_accessor_key
from app.api.base_view import BaseView
from app.api.docs import swagger_doc
from app.core.config import settings
from app.errors import parse_json_or_bad_request
from app.schemas import (
    AdminBanRequest,
    AdminBanResponse,
    AdminTopupRequest,
    AdminTopupResponse,
    BotActionRequest,
    BotSessionQueryRequest,
    BotTimeoutRequest,
    GroupLobbyJoinRequest,
    GroupLobbyOpenRequest,
    GroupLobbyQueryRequest,
    GroupLobbyStartRequest,
    GroupPlayerStopRequest,
    GroupSessionSnapshotCanonicalResponse,
    GroupSessionSnapshotResponse,
    SingleSessionStartRequest,
    SingleSessionStopRequest,
)


BOT_SNAPSHOT_RESPONSE_MODEL = (
    GroupSessionSnapshotResponse
    if settings.bot_snapshot_include_legacy_fields
    else GroupSessionSnapshotCanonicalResponse
)


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
