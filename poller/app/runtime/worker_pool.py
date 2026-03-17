"""Worker pool helpers for runtime update processing."""
import asyncio


async def cancel_tasks(tasks: list[asyncio.Task[None]]) -> None:
    """Cancel tasks and wait for their termination."""
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)
