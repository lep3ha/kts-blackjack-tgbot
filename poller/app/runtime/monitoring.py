"""Runtime task monitoring helpers."""
import asyncio


async def wait_for_runtime_failure(
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
