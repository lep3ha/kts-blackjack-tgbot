"""Ingress-to-worker dispatch helpers."""

from app.runtime.backpressure import QueueBackpressureMonitor
from app.runtime.intake_queue import BoundedUpdateQueue
from app.runtime.partitioning import resolve_partition_index


async def dispatch_updates(
    intake_queue: BoundedUpdateQueue,
    ingress_backpressure: QueueBackpressureMonitor,
    worker_queues: list[BoundedUpdateQueue],
    worker_backpressure: list[QueueBackpressureMonitor],
) -> None:
    """Route updates from ingress queue to per-worker partitions."""
    while True:
        item = await intake_queue.get()
        if item is None:
            for worker_queue in worker_queues:
                await worker_queue.close(consumer_count=1)
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
