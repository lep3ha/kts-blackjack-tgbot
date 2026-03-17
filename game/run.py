"""Entry point for the game service."""
import asyncio
import logging
import sys

from aiohttp import web

from app.main import init_app
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the application."""
    try:
        app = await init_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, settings.host, settings.port)
        await site.start()
        
        logger.info(
            f"{settings.app_name} started on http://{settings.host}:{settings.port}"
        )
        
        # Keep the server running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
