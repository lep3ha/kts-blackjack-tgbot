"""Common API/domain errors and payload validation helpers."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError


class ApiError(Exception):
    """Base API exception mapped to a JSON response by middleware."""

    def __init__(self, message: str, status: int = 400, code: str = "api_error"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


class NotFoundError(ApiError):
    def __init__(self, message: str):
        super().__init__(message=message, status=404, code="not_found")


class BadRequestError(ApiError):
    def __init__(self, message: str):
        super().__init__(message=message, status=400, code="bad_request")


class AuthorizationError(ApiError):
    def __init__(self, message: str):
        super().__init__(message=message, status=403, code="authorization_error")


class StateConflictError(ApiError):
    def __init__(self, message: str):
        super().__init__(message=message, status=409, code="state_conflict")


class StateTransitionError(StateConflictError):
    """Raised when a state-machine event is not allowed from current state."""


class StaleTurnError(ApiError):
    def __init__(self, message: str):
        super().__init__(message=message, status=409, code="stale_turn")


class GameLogicError(ApiError):
    def __init__(self, message: str):
        super().__init__(message=message, status=422, code="game_logic_error")


def parse_json_or_bad_request(raw: Any, schema_cls):
    """Validate incoming payload against a schema or raise BadRequestError."""
    try:
        return schema_cls.model_validate(raw)
    except ValidationError as exc:
        raise BadRequestError(str(exc)) from exc
