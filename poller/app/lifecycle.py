"""Application lifecycle primitives."""
import asyncio
import contextlib
import logging

from app.core.config import Settings
from app.core.resources import AsyncResource
from app.runtime.runner import PollingRunner

logger = logging.getLogger(__name__)


class PollerApplication:
    """Minimal poller application lifecycle coordinator."""

    def __init__(
        self,
        settings: Settings,
        polling_runner: PollingRunner,
        resources: list[AsyncResource] | None = None,
    ) -> None:
        self.settings = settings
        self.polling_runner = polling_runner
        self.resources = resources or []
        self._shutdown_event = asyncio.Event()
        self._runner_task: asyncio.Task[None] | None = None
        self._started = False

    async def start(self) -> None:
        """Start application components."""
        if self._started:
            return

        logger.info("Starting %s", self.settings.app_name)
        for resource in self.resources:
            logger.info("Starting resource %s", type(resource).__name__)
            await resource.start()
        self._runner_task = asyncio.create_task(
            self.polling_runner.run(self._shutdown_event),
            name="telegram-polling-runner",
        )
        self._started = True

    async def stop(self) -> None:
        """Stop application components."""
        if not self._started:
            return

        logger.info("Stopping %s", self.settings.app_name)
        self._shutdown_event.set()

        if self._runner_task is not None:
            try:
                await asyncio.wait_for(
                    self._runner_task,
                    timeout=self.settings.shutdown_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("Polling runner did not stop in time, cancelling task")
                self._runner_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._runner_task
            except Exception as error:
                logger.error("Polling runner stopped with error: %s", error)

        for resource in reversed(self.resources):
            logger.info("Stopping resource %s", type(resource).__name__)
            await resource.stop()

        self._started = False

    async def wait_for_shutdown(self) -> None:
        """Block until the application receives a shutdown signal."""
        if self._runner_task is None:
            await self._shutdown_event.wait()
            return

        shutdown_wait_task = asyncio.create_task(self._shutdown_event.wait())
        done, pending = await asyncio.wait(
            {shutdown_wait_task, self._runner_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        if self._runner_task in done:
            self._shutdown_event.set()
            await self._runner_task
