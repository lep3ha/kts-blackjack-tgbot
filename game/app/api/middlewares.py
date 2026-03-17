"""aiohttp middlewares for API error handling."""
from __future__ import annotations

import json
import logging

from aiohttp import web
from pydantic import ValidationError

from app.errors import ApiError

logger = logging.getLogger(__name__)


def _error_response(*, code: str, message: str, status: int, details=None) -> web.Response:
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details is not None:
        payload["error"]["details"] = details
    return web.json_response(payload, status=status)


@web.middleware
async def error_middleware(request: web.Request, handler):
    """Convert framework/domain exceptions into consistent JSON errors."""
    try:
        response = await handler(request)
        if response.status == 404:
            return _error_response(code="not_found", message="Not found", status=404)
        return response
    except ApiError as exc:
        return _error_response(code=exc.code, message=exc.message, status=exc.status)
    except ValidationError as exc:
        return _error_response(
            code="validation_error",
            message="Validation failed",
            status=400,
            details=exc.errors(),
        )
    except json.JSONDecodeError:
        return _error_response(code="bad_json", message="Invalid JSON body", status=400)
    except web.HTTPException as exc:
        return _error_response(code="http_error", message=exc.reason, status=exc.status)
    except Exception:
        logger.exception("Unhandled server error")
        return _error_response(code="internal_error", message="Internal server error", status=500)
