"""Producer-side polling and queueing helpers."""
import asyncio
import logging
from typing import Any

from app.runtime.backpressure import QueueBackpressureMonitor
from app.runtime.intake_queue import BoundedUpdateQueue
from app.runtime.intake_queue import QueuedUpdate
from app.telegram.client import TelegramPollingClient
from app.telegram.errors import FatalTelegramError
from app.telegram.errors import RetryableTelegramError

logger = logging.getLogger(__name__)


async def produce_updates(
    client: TelegramPollingClient,
    session: Any,
    shutdown_event: asyncio.Event,
    intake_queue: BoundedUpdateQueue,
    ingress_backpressure: QueueBackpressureMonitor,
    offset: int | None,
    failed_runtime_task: asyncio.Task[None],
) -> int | None:
    """Fetch updates from Telegram and enqueue them for processing."""
    attempt = 0
    sequence_number = 0

    while not shutdown_event.is_set():
        if failed_runtime_task.done():
            await failed_runtime_task

        try:
            updates = await client.fetch_updates(session=session, offset=offset)
            attempt = 0
        except RetryableTelegramError as error:
            delay = client.retry_policy.next_delay(
                attempt=attempt,
                retry_after=error.retry_after,
            )
            attempt += 1
            logger.warning("Polling retry in %.2fs: %s", delay, error)
            await wait_or_shutdown(shutdown_event, delay)
            continue
        except FatalTelegramError:
            logger.exception("Fatal Telegram polling error")
            raise

        if not updates:
            await asyncio.sleep(0)
            continue

        for update in updates:
            if shutdown_event.is_set():
                break

            next_offset = None
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                next_offset = update_id + 1
            sequence_number += 1

            await enqueue_update(
                intake_queue=intake_queue,
                backpressure_monitor=ingress_backpressure,
                queued_update=QueuedUpdate(
                    sequence_number=sequence_number,
                    update=update,
                    next_offset=next_offset,
                ),
                failed_runtime_task=failed_runtime_task,
            )

            if next_offset is not None:
                offset = next_offset

    return offset


async def enqueue_update(
    intake_queue: BoundedUpdateQueue,
    backpressure_monitor: QueueBackpressureMonitor,
    queued_update: QueuedUpdate,
    failed_runtime_task: asyncio.Task[None],
) -> None:
    """Enqueue an update or fail fast if runtime routing stops with error."""
    backpressure_monitor.before_put(intake_queue)
    enqueue_task = asyncio.create_task(intake_queue.put(queued_update))
    done, _ = await asyncio.wait(
        {enqueue_task, failed_runtime_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if failed_runtime_task in done:
        enqueue_task.cancel()
        await asyncio.gather(enqueue_task, return_exceptions=True)
        await failed_runtime_task
        return

    await enqueue_task


async def wait_or_shutdown(
    shutdown_event: asyncio.Event,
    delay: float,
) -> None:
    """Sleep until delay elapses or shutdown is requested."""
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
    except asyncio.TimeoutError:
        return
