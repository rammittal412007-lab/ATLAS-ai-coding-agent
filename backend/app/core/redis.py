import json
from typing import Any, AsyncGenerator, Optional

import redis.asyncio as aioredis
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class RedisClient:
    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def connect(self):
        self._client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.REDIS_POOL_SIZE,
        )
        await self._client.ping()

    async def disconnect(self):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError("Redis not connected")
        return self._client

    async def get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def set(self, key: str, value: str, expire: Optional[int] = None):
        await self.client.set(key, value, ex=expire)

    async def delete(self, key: str):
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self.client.exists(key))

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: Any, expire: Optional[int] = None):
        await self.set(key, json.dumps(value), expire=expire)

    async def publish(self, channel: str, message: Any):
        payload = json.dumps(message) if not isinstance(message, str) else message
        await self.client.publish(channel, payload)

    async def subscribe(self, channel: str) -> AsyncGenerator[Any, None]:
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        yield json.loads(message["data"])
                    except json.JSONDecodeError:
                        yield message["data"]
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    async def lpush(self, key: str, *values: str):
        await self.client.lpush(key, *values)

    async def lrange(self, key: str, start: int, end: int):
        return await self.client.lrange(key, start, end)

    async def hset(self, name: str, mapping: dict):
        await self.client.hset(name, mapping=mapping)

    async def hgetall(self, name: str) -> dict:
        return await self.client.hgetall(name)


redis_client = RedisClient()


async def get_redis() -> RedisClient:
    return redis_client
