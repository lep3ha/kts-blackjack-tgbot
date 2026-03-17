import asyncio
import json
import logging
import time
from contextlib import suppress
from datetime import datetime
from datetime import timezone

from redis.asyncio import Redis

from app.timers.interfaces import TimeoutExecutor
from app.timers.models import TimeoutTask


logger = logging.getLogger(__name__)


class RedisTimerWorker:
    def __init__(
        self,
        *,
        redis_client: Redis,
        timeout_executor: TimeoutExecutor,
        retention_seconds: int,
        poll_interval_seconds: float,
        claim_ttl_seconds: int,
        key_prefix: str = "timer",
    ) -> None:
        self._redis = redis_client
        self._timeout_executor = timeout_executor
        self._retention_seconds = retention_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._claim_ttl_seconds = claim_ttl_seconds
        self._key_prefix = key_prefix
        self._loop_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._loop_task is not None and not self._loop_task.done():
            return

        self._loop_task = asyncio.create_task(self._run_loop(), name="redis-timer-worker")

    async def stop(self) -> None:
        if self._loop_task is None:
            return

        self._loop_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._loop_task
        self._loop_task = None

    async def schedule_timeout(
        self,
        *,
        chat_id: str,
        chat_type: str,
        session_id: int,
        turn_version: int,
        due_at: datetime,
    ) -> None:
        task = TimeoutTask(
            chat_id=chat_id,
            chat_type=chat_type,
            session_id=session_id,
            turn_version=turn_version,
            due_at=due_at,
        )

        if await self._redis.exists(self._done_key(task.timer_id)):
            return

        payload = {
            "chat_id": task.chat_id,
            "chat_type": task.chat_type,
            "session_id": task.session_id,
            "turn_version": task.turn_version,
            "due_at": task.due_at.astimezone(timezone.utc).isoformat(),
        }

        await self._redis.set(
            name=self._payload_key(task.timer_id),
            value=json.dumps(payload),
            ex=self._retention_seconds,
        )
        await self._redis.zadd(
            self._index_key(),
            {task.timer_id: task.due_at.timestamp()},
        )

    async def cancel_timeout(self, *, chat_id: str, session_id: int, turn_version: int) -> None:
        timer_id = self._timer_id(chat_id=chat_id, session_id=session_id, turn_version=turn_version)
        await self._redis.zrem(self._index_key(), timer_id)
        await self._redis.delete(
            self._payload_key(timer_id),
            self._claim_key(timer_id),
        )

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._process_due_tasks()
            except Exception:
                logger.exception("Timer worker polling failed")
            await asyncio.sleep(self._poll_interval_seconds)

    async def _process_due_tasks(self) -> None:
        now_ts = time.time()
        timer_ids = await self._redis.zrangebyscore(self._index_key(), min="-inf", max=now_ts)
        for raw_timer_id in timer_ids:
            timer_id = raw_timer_id.decode("utf-8") if isinstance(raw_timer_id, bytes) else str(raw_timer_id)
            await self._process_timer(timer_id)

    async def _process_timer(self, timer_id: str) -> None:
        if await self._redis.exists(self._done_key(timer_id)):
            await self._redis.zrem(self._index_key(), timer_id)
            await self._redis.delete(self._payload_key(timer_id))
            return

        claimed = await self._redis.set(
            name=self._claim_key(timer_id),
            value="1",
            ex=self._claim_ttl_seconds,
            nx=True,
        )
        if not claimed:
            return

        try:
            payload_raw = await self._redis.get(self._payload_key(timer_id))
            if payload_raw is None:
                await self._redis.zrem(self._index_key(), timer_id)
                return

            payload_text = payload_raw.decode("utf-8") if isinstance(payload_raw, bytes) else str(payload_raw)
            payload = json.loads(payload_text)
            task = TimeoutTask(
                chat_id=str(payload["chat_id"]),
                chat_type=str(payload.get("chat_type", "group")),
                session_id=int(payload["session_id"]),
                turn_version=int(payload["turn_version"]),
                due_at=datetime.fromisoformat(str(payload["due_at"])),
            )

            await self._timeout_executor.execute_timeout(task)
            await self._redis.set(
                name=self._done_key(timer_id),
                value="1",
                ex=self._retention_seconds,
                nx=True,
            )
            await self._redis.zrem(self._index_key(), timer_id)
            await self._redis.delete(self._payload_key(timer_id))
        except Exception:
            logger.exception("Timer timeout execution failed timer_id=%s", timer_id)
            await self._redis.zadd(self._index_key(), {timer_id: time.time() + 1.0})
        finally:
            await self._redis.delete(self._claim_key(timer_id))

    @staticmethod
    def _timer_id(*, chat_id: str, session_id: int, turn_version: int) -> str:
        return f"{chat_id}:{session_id}:{turn_version}"

    def _index_key(self) -> str:
        return f"{self._key_prefix}:index"

    def _payload_key(self, timer_id: str) -> str:
        return f"{self._key_prefix}:payload:{timer_id}"

    def _claim_key(self, timer_id: str) -> str:
        return f"{self._key_prefix}:claim:{timer_id}"

    def _done_key(self, timer_id: str) -> str:
        return f"{self._key_prefix}:done:{timer_id}"
