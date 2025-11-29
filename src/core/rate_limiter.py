import time
from typing import Optional

from redis.asyncio import Redis

from src.core.exceptions import RateLimitExceededError


class RateLimiter:
    """Token bucket rate limiter using Redis sorted sets."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def check_rate_limit(
        self,
        user_id: str,
        limit_per_second: int,
        burst_limit: int,
    ) -> dict:
        """
        Check if request is within rate limits using sliding window.

        Args:
            user_id: Unique identifier for the user
            limit_per_second: Maximum requests per second
            burst_limit: Maximum burst capacity

        Returns:
            dict with rate limit headers

        Raises:
            RateLimitExceededError if limit exceeded
        """
        key = f"ratelimit:{user_id}"
        now = time.time()
        window_start = now - 1  # 1 second sliding window

        # Use transaction=True for atomic execution of all commands
        # This ensures the count we get reflects our cleanup and add operations
        pipe = self.redis.pipeline(transaction=True)

        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries in window
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {f"{now}:{id(now)}": now})
        # Set expiry on key (cleanup)
        pipe.expire(key, 2)

        results = await pipe.execute()
        current_count = results[1]

        # Calculate headers
        remaining = max(0, burst_limit - current_count - 1)
        reset_time = int(now) + 1

        headers = {
            "X-RateLimit-Limit": str(limit_per_second),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
        }

        # Check if exceeded
        if current_count >= burst_limit:
            headers["Retry-After"] = "1"
            raise RateLimitExceededError(retry_after=1)

        return headers


async def check_rate_limit(
    redis: Redis,
    user_id: str,
    rate_limit_per_second: int,
    rate_limit_burst: int,
) -> dict:
    """
    Convenience function to check rate limits.

    Returns headers dict to add to response.
    """
    limiter = RateLimiter(redis)
    return await limiter.check_rate_limit(
        user_id=user_id,
        limit_per_second=rate_limit_per_second,
        burst_limit=rate_limit_burst,
    )


async def check_login_rate_limit(
    redis: Redis,
    client_ip: str,
    limit_per_minute: int,
    burst_limit: int,
) -> dict:
    """
    Check IP-based rate limit for login endpoint.

    Uses a 60-second sliding window instead of 1 second for login attempts.
    This helps prevent brute force attacks.

    Returns headers dict to add to response.
    """
    key = f"login_ratelimit:{client_ip}"
    now = time.time()
    window_start = now - 60  # 60 second sliding window

    # Use transaction=True for atomic execution of all commands
    # This ensures the count we get reflects our cleanup and add operations
    pipe = redis.pipeline(transaction=True)

    # Remove old entries outside the window
    pipe.zremrangebyscore(key, 0, window_start)
    # Count current entries in window
    pipe.zcard(key)
    # Add current request
    pipe.zadd(key, {f"{now}:{id(now)}": now})
    # Set expiry on key (cleanup after 2 minutes)
    pipe.expire(key, 120)

    results = await pipe.execute()
    current_count = results[1]

    # Calculate headers
    remaining = max(0, burst_limit - current_count - 1)
    reset_time = int(now) + 60

    headers = {
        "X-RateLimit-Limit": str(limit_per_minute),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_time),
    }

    # Check if exceeded
    if current_count >= burst_limit:
        headers["Retry-After"] = "60"
        raise RateLimitExceededError(retry_after=60)

    return headers
