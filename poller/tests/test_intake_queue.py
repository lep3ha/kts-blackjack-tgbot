import asyncio

from app.runtime.intake_queue import BoundedUpdateQueue
from app.runtime.intake_queue import QueuedUpdate


def test_bounded_update_queue_put_get_and_close() -> None:
    async def scenario() -> None:
        queue = BoundedUpdateQueue(max_size=2)

        await queue.put(
            QueuedUpdate(sequence_number=1, update={"update_id": 1}, next_offset=2)
        )
        item = await queue.get()
        assert item is not None
        assert item.sequence_number == 1
        queue.task_done()

        await queue.close(consumer_count=1)
        sentinel = await queue.get()
        assert sentinel is None

    asyncio.run(scenario())
