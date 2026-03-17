"""Main application factory."""
import logging

from aiohttp import web

from app.accessors import setup_accessors
from app.api import setup_routes
from app.api.middlewares import error_middleware
from app.db import db

logger = logging.getLogger(__name__)


async def init_app() -> web.Application:
    """Initialize and configure the application."""
    app = web.Application(middlewares=[error_middleware])
    setup_accessors(app)

    app.on_startup.append(lambda app: db.init())
    app.on_cleanup.append(lambda app: db.close())

    setup_routes(app)

    logger.info("Application initialized")
    return app
