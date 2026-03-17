"""Worker-consumer helpers for downstream delivery and offset commit."""
import logging

from app.runtime.ack_tracker import OffsetCommitTracker
from app.runtime.backpressure import QueueBackpressureMonitor
from app.runtime.intake_queue import BoundedUpdateQueue
from app.storage.offset_store import OffsetStore
from app.downstream.sink import UpdateSink

logger = logging.getLogger(__name__)


async def consume_updates(
    worker_queue: BoundedUpdateQueue,
    worker_backpressure: QueueBackpressureMonitor,
    commit_tracker: OffsetCommitTracker,
    update_sink: UpdateSink,
    offset_store: OffsetStore,
) -> None:
    """Process queued updates concurrently and commit contiguous offsets."""
    while True:
        item = await worker_queue.get()
        if item is None:
            return

        try:
            await update_sink.handle(item.update)
            committable_offset = await commit_tracker.mark_processed(
                sequence_number=item.sequence_number,
                next_offset=item.next_offset,
            )
            if committable_offset is not None:
                await offset_store.save_offset(committable_offset)
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
