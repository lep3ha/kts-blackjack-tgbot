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


async def swagger_ui(_request: web.Request) -> web.Response:
    """Возвращает Swagger UI, который использует /openapi.json как источник схемы."""
    html = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Game Service API Docs</title>
    <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css\" />
</head>
<body>
    <div id=\"swagger-ui\"></div>
    <script src=\"https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js\"></script>
    <script>
        window.onload = () => {
            SwaggerUIBundle({
                url: '/openapi.json',
                dom_id: '#swagger-ui',
            });
        };
    </script>
</body>
</html>
"""
    return web.Response(text=html, content_type="text/html")


def setup_routes(app: web.Application) -> None:
    """Регистрирует минимальный набор рабочих маршрутов."""
    app.router.add_get("/health", health_check)
    app.router.add_get("/openapi.json", openapi_spec)
    app.router.add_get("/docs", swagger_ui)
    setup_blackjack_routes(app)
