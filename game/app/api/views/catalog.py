"""Catalog API views for players, decks and sessions."""
from __future__ import annotations

from aiohttp import web

from app.accessors import catalog_accessor_key
from app.api.base_view import BaseView
from app.api.docs import swagger_doc
from app.schemas import (
    DeckCreateRequest,
    DeckCreateResponse,
    PlayerCreateRequest,
    PlayerCreateResponse,
    SeatCreateRequest,
    SeatCreateResponse,
    SessionCreateRequest,
    SessionCreateResponse,
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


class PlayerByTelegramView(BaseView):
    @swagger_doc(
        summary="Get player by telegram id",
        description="Returns player profile including current bank by telegram_id.",
        tags=["catalog"],
        response_model=PlayerCreateResponse,
    )
    async def get(self) -> web.Response:
        telegram_id = self.request.match_info.get("telegram_id", "").strip()
        if not telegram_id:
            raise web.HTTPBadRequest(text="telegram_id is required")

        accessor = self.request.app[catalog_accessor_key]
        data = await accessor.get_player_by_telegram_id(telegram_id)
        return self.success_response(data)


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
