"""Backpressure state tracking for bounded runtime queues."""
import logging

from app.runtime.intake_queue import BoundedUpdateQueue


class QueueBackpressureMonitor:
    """Tracks pressure transitions for a single queue."""

    def __init__(self, queue_name: str) -> None:
        self.queue_name = queue_name
        self._pressure_active = False
        self._logger = logging.getLogger(__name__)

    def before_put(self, queue: BoundedUpdateQueue) -> None:
        """Record entering pressure mode when the queue is full."""
        if queue.is_full() and not self._pressure_active:
            self._pressure_active = True
            self._logger.warning(
                "Backpressure enabled on %s queue: size=%s/%s",
                self.queue_name,
                queue.qsize(),
                queue.max_size,
            )

    def after_task_done(self, queue: BoundedUpdateQueue) -> None:
        """Record recovery when the queue is no longer full."""
        if self._pressure_active and not queue.is_full():
            self._pressure_active = False
            self._logger.info(
                "Backpressure cleared on %s queue: size=%s/%s",
                self.queue_name,
                queue.qsize(),
                queue.max_size,
            )
