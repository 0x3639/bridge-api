import json
from typing import Any, Callable, Optional

from redis.asyncio import Redis


class CacheService:
    """Redis caching service."""

    def __init__(self, redis: Redis):
        self.redis = redis
        self.prefix = "cache"

    def _key(self, key: str) -> str:
        """Generate full cache key with prefix."""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """
        Get cached value.

        Returns None if not found or expired.
        """
        data = await self.redis.get(self._key(key))
        if data:
            return json.loads(data)
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        """
        Set cached value with TTL in seconds.

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds
        """
        await self.redis.setex(
            self._key(key),
            ttl,
            json.dumps(value, default=str),
        )

    async def delete(self, key: str) -> None:
        """Delete a cached value."""
        await self.redis.delete(self._key(key))

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching pattern."""
        full_pattern = self._key(pattern)
        keys = []
        async for key in self.redis.scan_iter(match=full_pattern):
            keys.append(key)
        if keys:
            await self.redis.delete(*keys)

    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl: int = 60,
    ) -> Any:
        """
        Get cached value or compute and cache it.

        Args:
            key: Cache key
            factory: Async callable that returns the value to cache
            ttl: Time to live in seconds

        Returns:
            Cached or computed value
        """
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await factory()
        await self.set(key, value, ttl)
        return value

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        return await self.redis.exists(self._key(key)) > 0

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for a key. Returns -2 if key doesn't exist."""
        return await self.redis.ttl(self._key(key))

    async def invalidate_status_caches(self) -> None:
        """
        Invalidate all caches related to orchestrator status.

        Call this after status data is updated to ensure consistency
        across the status endpoint and statistics endpoints.
        """
        # Use pipeline for atomic deletion of related caches
        pipe = self.redis.pipeline(transaction=True)

        # Delete main status cache
        pipe.delete(self._key("status:current"))

        # Delete statistics caches that depend on status data
        # These use patterns like stats:bridge:*, stats:uptime:*, stats:networks:*
        # We'll delete specific known keys rather than scanning to avoid performance issues
        for hours in [1, 6, 12, 24, 48, 168, 720]:  # Common hour values
            for interval in [15, 30, 60]:  # Common intervals
                pipe.delete(self._key(f"stats:bridge:{hours}:{interval}"))
            pipe.delete(self._key(f"stats:uptime:{hours}"))
            pipe.delete(self._key(f"stats:networks:{hours}"))

        await pipe.execute()

    async def invalidate_user_cache(self, user_id: str) -> None:
        """
        Invalidate caches related to a specific user.

        Call this after user data is updated.
        """
        await self.delete(f"user:{user_id}")
