"""Базовые API routes для текущего состояния проекта."""

from aiohttp import web

from app.api.views import BLACKJACK_VIEW_ROUTES, setup_blackjack_routes
from app.api.docs import build_view_paths


async def health_check(request: web.Request) -> web.Response:
    """Проверяет, что приложение отвечает на HTTP-запросы."""
    return web.json_response({"success": True, "data": {"status": "ok"}})


async def openapi_spec(_request: web.Request) -> web.Response:
    """Возвращает минимальную OpenAPI-спецификацию, собранную из swagger-декораторов."""
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Game Service API",
            "version": "1.0.0",
        },
        "paths": {
            "/health": {
                "get": {
                    "summary": "Health check",
                    "tags": ["service"],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean", "const": True},
                                            "data": {
                                                "type": "object",
                                                "properties": {"status": {"type": "string"}},
                                                "required": ["status"],
                                            },
                                        },
                                        "required": ["success", "data"],
                                    }
                                }
                            },
                        }
                    },
                }
            },
            **build_view_paths(BLACKJACK_VIEW_ROUTES),
        },
    }
    return web.json_response(spec)


def setup_routes(app: web.Application) -> None:
    """Регистрирует минимальный набор рабочих маршрутов."""
    app.router.add_get("/health", health_check)
    app.router.add_get("/openapi.json", openapi_spec)
    setup_blackjack_routes(app)
