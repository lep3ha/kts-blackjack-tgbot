"""Polling loop orchestration for Telegram updates."""
import asyncio
import logging

from aiohttp import ClientSession

from app.downstream.sink import UpdateSink
from app.runtime.ack_tracker import OffsetCommitTracker
from app.runtime.backpressure import QueueBackpressureMonitor
from app.runtime.intake_queue import BoundedUpdateQueue
from app.runtime.intake_queue import QueuedUpdate
from app.runtime.partitioning import resolve_partition_index
from app.runtime.worker_pool import cancel_tasks
from app.storage.offset_store import OffsetStore
from app.telegram.client import TelegramPollingClient
from app.telegram.errors import FatalTelegramError
from app.telegram.errors import RetryableTelegramError

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
            self._dispatch_updates(
                intake_queue=intake_queue,
                ingress_backpressure=ingress_backpressure,
                worker_queues=worker_queues,
                worker_backpressure=worker_backpressure,
            ),
            name="telegram-update-dispatcher",
        )
        worker_tasks = [
            asyncio.create_task(
                self._consume_updates(
                    worker_queue=worker_queues[index],
                    worker_backpressure=worker_backpressure[index],
                    commit_tracker=commit_tracker,
                ),
                name=f"telegram-update-consumer-{index + 1}",
            )
            for index in range(self.worker_count)
        ]
        runtime_tasks = [dispatcher_task, *worker_tasks]
        failed_runtime_task = asyncio.create_task(
            self._wait_for_runtime_failure(runtime_tasks),
            name="telegram-runtime-monitor",
        )
        failed = False

        try:
            async with ClientSession() as session:
                await self._produce_updates(
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

    async def _produce_updates(
        self,
        session: ClientSession,
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
                updates = await self.client.fetch_updates(session=session, offset=offset)
                attempt = 0
            except RetryableTelegramError as error:
                delay = self.client.retry_policy.next_delay(
                    attempt=attempt,
                    retry_after=error.retry_after,
                )
                attempt += 1
                logger.warning("Polling retry in %.2fs: %s", delay, error)
                await self._wait_or_shutdown(shutdown_event, delay)
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

                await self._enqueue_update(
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

    async def _enqueue_update(
        self,
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

    async def _dispatch_updates(
        self,
        intake_queue: BoundedUpdateQueue,
        ingress_backpressure: QueueBackpressureMonitor,
        worker_queues: list[BoundedUpdateQueue],
        worker_backpressure: list[QueueBackpressureMonitor],
    ) -> None:
        """Route updates from ingress queue to per-worker partitions."""
        while True:
            item = await intake_queue.get()
            if item is None:
                try:
                    for worker_queue in worker_queues:
                        await worker_queue.close(consumer_count=1)
                finally:
                    return

            try:
                partition_index = resolve_partition_index(
                    update=item.update,
                    worker_count=len(worker_queues),
                )
                worker_backpressure[partition_index].before_put(worker_queues[partition_index])
                await worker_queues[partition_index].put(item)
            finally:
                intake_queue.task_done()
                ingress_backpressure.after_task_done(intake_queue)

    async def _consume_updates(
        self,
        worker_queue: BoundedUpdateQueue,
        worker_backpressure: QueueBackpressureMonitor,
        commit_tracker: OffsetCommitTracker,
    ) -> None:
        """Process queued updates concurrently and commit contiguous offsets."""
        while True:
            item = await worker_queue.get()
            if item is None:
                return

            try:
                await self.update_sink.handle(item.update)
                committable_offset = await commit_tracker.mark_processed(
                    sequence_number=item.sequence_number,
                    next_offset=item.next_offset,
                )
                if committable_offset is not None:
                    await self.offset_store.save_offset(committable_offset)
            except Exception:
                logger.exception(
                    "Downstream delivery failed, offset will not be acknowledged: update_id=%s sequence_number=%s next_offset=%s",
                    item.update.get("update_id"),
                    item.sequence_number,
                    item.next_offset,
                )
                raise
            finally:
                worker_queue.task_done()
                worker_backpressure.after_task_done(worker_queue)

    async def _wait_for_runtime_failure(
        self,
        runtime_tasks: list[asyncio.Task[None]],
    ) -> None:
        """Wait until any dispatcher or worker task fails unexpectedly."""
        done, pending = await asyncio.wait(
            set(runtime_tasks),
            return_when=asyncio.FIRST_EXCEPTION,
        )

        for task in done:
            await task

        for task in pending:
            if task.done():
                await task

    async def _wait_or_shutdown(
        self,
        shutdown_event: asyncio.Event,
        delay: float,
    ) -> None:
        """Sleep until delay elapses or shutdown is requested."""
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            return
