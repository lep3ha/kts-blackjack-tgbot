import json

from redis.asyncio import Redis

from app.state.models import SessionContext


class RedisDedupStore:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def check_and_mark(self, key: str, ttl_seconds: int) -> bool:
        """Return True for first-seen key and False for duplicates."""
        created = await self._redis.set(name=key, value="1", ex=ttl_seconds, nx=True)
        return bool(created)


class RedisSessionContextStore:
    def __init__(self, redis_client: Redis, key_prefix: str = "session_ctx") -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix

    async def get(self, chat_id: str) -> SessionContext | None:
        raw = await self._redis.get(self._build_key(chat_id))
        if raw is None:
            return None

        payload = json.loads(raw)
        return SessionContext.model_validate(payload)

    async def set(self, chat_id: str, context: SessionContext, ttl_seconds: int) -> None:
        await self._redis.set(
            name=self._build_key(chat_id),
            value=context.model_dump_json(),
            ex=ttl_seconds,
        )

    def _build_key(self, chat_id: str) -> str:
        return f"{self._key_prefix}:{chat_id}"
