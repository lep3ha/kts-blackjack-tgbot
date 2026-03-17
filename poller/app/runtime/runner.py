"""Polling loop orchestration for Telegram updates."""
import asyncio
import logging

from aiohttp import ClientSession

from app.runtime.consumer import consume_updates
from app.runtime.dispatcher import dispatch_updates
from app.runtime.monitoring import wait_for_runtime_failure
from app.runtime.producer import produce_updates
from app.downstream.sink import UpdateSink
from app.runtime.ack_tracker import OffsetCommitTracker
from app.runtime.backpressure import QueueBackpressureMonitor
from app.runtime.intake_queue import BoundedUpdateQueue
from app.runtime.worker_pool import cancel_tasks
from app.storage.offset_store import OffsetStore
from app.telegram.client import TelegramPollingClient

logger = logging.getLogger(__name__)


class PollingRunner:
    """Runs the Telegram long-polling loop until shutdown."""

    def __init__(
        self,
        client: TelegramPollingClient,
        offset_store: OffsetStore,
        update_sink: UpdateSink,
        queue_max_size: int,
        worker_count: int,
    ) -> None:
        if worker_count <= 0:
            raise ValueError("Worker count must be greater than zero")

        self.client = client
        self.offset_store = offset_store
        self.update_sink = update_sink
        self.queue_max_size = queue_max_size
        self.worker_count = worker_count

    async def run(self, shutdown_event: asyncio.Event) -> None:
        """Run polling until a shutdown signal is received."""
        fetch_offset = await self.offset_store.load_offset()
        intake_queue = BoundedUpdateQueue(max_size=self.queue_max_size)
        ingress_backpressure = QueueBackpressureMonitor(queue_name="ingress")
        worker_queue_size = max(1, self.queue_max_size // self.worker_count)
        worker_queues = [
            BoundedUpdateQueue(max_size=worker_queue_size)
            for _ in range(self.worker_count)
        ]
        worker_backpressure = [
            QueueBackpressureMonitor(queue_name=f"worker-{index + 1}")
            for index in range(self.worker_count)
        ]
        commit_tracker = OffsetCommitTracker(initial_offset=fetch_offset)
        dispatcher_task = asyncio.create_task(
            dispatch_updates(
                intake_queue=intake_queue,
                ingress_backpressure=ingress_backpressure,
                worker_queues=worker_queues,
                worker_backpressure=worker_backpressure,
            ),
            name="telegram-update-dispatcher",
        )
        worker_tasks = [
            asyncio.create_task(
                consume_updates(
                    worker_queue=worker_queues[index],
                    worker_backpressure=worker_backpressure[index],
                    commit_tracker=commit_tracker,
                    update_sink=self.update_sink,
                    offset_store=self.offset_store,
                ),
                name=f"telegram-update-consumer-{index + 1}",
            )
            for index in range(self.worker_count)
        ]
        runtime_tasks = [dispatcher_task, *worker_tasks]
        failed_runtime_task = asyncio.create_task(
            wait_for_runtime_failure(runtime_tasks),
            name="telegram-runtime-monitor",
        )
        failed = False

        try:
            async with ClientSession() as session:
                await produce_updates(
                    client=self.client,
                    session=session,
                    shutdown_event=shutdown_event,
                    intake_queue=intake_queue,
                    ingress_backpressure=ingress_backpressure,
                    offset=fetch_offset,
                    failed_runtime_task=failed_runtime_task,
                )
        except Exception:
            failed = True
            raise
        finally:
            if failed:
                await cancel_tasks(runtime_tasks)
                failed_runtime_task.cancel()
                await asyncio.gather(failed_runtime_task, return_exceptions=True)
            else:
                logger.info("Shutdown requested, closing ingress queue for draining")
                await intake_queue.close(consumer_count=1)
                logger.info("Waiting for ingress queue to drain")
                await intake_queue.join()
                logger.info("Ingress queue drained")

                logger.info("Waiting for worker queues to drain")
                for worker_queue in worker_queues:
                    await worker_queue.join()
                logger.info("Worker queues drained")

                failed_runtime_task.cancel()
                await asyncio.gather(failed_runtime_task, return_exceptions=True)
                results = await asyncio.gather(*runtime_tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.exception("Runtime task failed", exc_info=result)
                        raise result
