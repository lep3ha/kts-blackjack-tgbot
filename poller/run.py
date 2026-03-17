"""Entry point for the poller service."""
import asyncio
import logging
import signal
import sys

from app.core.config import settings
from app.core.logging import configure_logging
from app.main import init_app

logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the poller service."""
    configure_logging(settings.debug)
    app = await init_app()
    stop_started = asyncio.Event()

    async def shutdown() -> None:
        if stop_started.is_set():
            return

        stop_started.set()
        await app.stop()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    try:
        await app.start()
        logger.info("%s bootstrap completed", settings.app_name)
        await app.wait_for_shutdown()
    except KeyboardInterrupt:
        await shutdown()
    except Exception as error:
        logger.exception("Unhandled error during service execution: %s", error)
        await shutdown()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
