"""Shared base class for aiohttp class-based views."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from aiohttp import web
from pydantic import BaseModel

from app.errors import BadRequestError, parse_json_or_bad_request


class BaseView(web.View):
    """Provides common helpers for JSON APIs."""

    def success_response(self, data: Any = None, *, status: int = 200) -> web.Response:
        return web.json_response({"success": True, "data": self._to_jsonable(data)}, status=status)

    async def parse_json(self, schema_cls):
        payload = await self.request.json()
        return parse_json_or_bad_request(payload, schema_cls)

    def parse_session_id(self) -> int:
        raw = self.request.match_info.get("session_id", "")
        try:
            value = int(raw)
        except ValueError as exc:
            raise BadRequestError("session_id must be an integer") from exc
        if value <= 0:
            raise BadRequestError("session_id must be positive")
        return value

    def _to_jsonable(self, value: Any):
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: self._to_jsonable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._to_jsonable(v) for v in value]
        if isinstance(value, tuple):
            return [self._to_jsonable(v) for v in value]
        return value
