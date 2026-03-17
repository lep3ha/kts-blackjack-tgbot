"""Gameplay API views for direct session control."""
from __future__ import annotations

from aiohttp import web

from app.accessors import blackjack_accessor_key
from app.api.base_view import BaseView
from app.api.docs import swagger_doc
from app.schemas import ActionRequest, SessionStateResponse, TimeoutRequest


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
