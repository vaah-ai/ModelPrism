"""Redis async connection management.

Provides:
- ``redis_client`` — the shared Redis connection (singleton)
- ``get_redis`` — FastAPI dependency returning the shared connection
- ``PubSubHelper`` — helper class for pub/sub operations
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
redis_client: AsyncRedis | None = None


async def init_redis() -> AsyncRedis:
    """Initialize the Redis connection pool and return the client.

    This is called during application startup.
    """
    global _pool, redis_client

    _pool = ConnectionPool.from_url(str(settings.redis_url))
    redis_client = AsyncRedis(connection_pool=_pool)
    logger.info("Redis connection pool initialized")
    return redis_client


async def close_redis() -> None:
    """Close the Redis connection pool.

    This is called during application shutdown.
    """
    global _pool, redis_client

    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None
        logger.info("Redis client closed")

    if _pool is not None:
        await _pool.disconnect()
        _pool = None
        logger.info("Redis connection pool disposed")


async def get_redis() -> AsyncIterator[AsyncRedis]:
    """FastAPI dependency that returns the shared Redis client."""
    if redis_client is None:
        raise RedisError("Redis client is not initialized")
    yield redis_client


async def verify_redis_connection() -> bool:
    """Verify Redis is reachable by sending a PING.

    Returns True if connected, False otherwise.
    """
    if redis_client is None:
        return False
    try:
        return await redis_client.ping()
    except RedisError:
        return False


class PubSubHelper:
    """Helper for Redis pub/sub operations.

    Provides typed publish/subscribe for channel-based messaging
    used by WebSocket broadcast and cross-instance communication.
    """

    def __init__(self, client: AsyncRedis) -> None:
        self._client = client

    async def publish(self, channel: str, message: dict[str, Any]) -> int:
        """Publish a JSON-encoded message to a channel.

        Returns the number of subscribers that received the message.
        """
        payload = json.dumps(message, default=str)
        return await self._client.publish(channel, payload)

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to a channel and yield decoded messages as they arrive."""
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message.get("data")
                    if isinstance(data, bytes):
                        yield json.loads(data.decode("utf-8"))
                    elif isinstance(data, str):
                        yield json.loads(data)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
