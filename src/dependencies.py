import hashlib
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload

from src.config import settings
from src.core.exceptions import AuthenticationError, AuthorizationError
from src.core.rate_limiter import check_rate_limit
from src.core.security import decode_session_jwt, hash_token
from src.models.token import ApiToken
from src.models.user import User

# Database engine and session with configurable connection pooling
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,  # Number of permanent connections
    max_overflow=settings.db_max_overflow,  # Additional connections under load
    pool_recycle=settings.db_pool_recycle,  # Recycle connections after this many seconds
    pool_pre_ping=settings.db_pool_pre_ping,  # Verify connections are alive before use
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Redis client
_redis_client: Optional[Redis] = None

# Security scheme
security = HTTPBearer(auto_error=False)


async def init_db() -> None:
    """Initialize database connection pool."""
    pass  # Engine is created at module level


async def close_db() -> None:
    """Close database connection pool."""
    await engine.dispose()


async def init_redis() -> None:
    """Initialize Redis connection."""
    global _redis_client
    _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> Redis:
    """Get Redis client dependency."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return _redis_client


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate authentication and return current user.

    Supports both:
    - API tokens (ora_xxx format)
    - Session JWTs (for login flow)
    """
    if credentials is None:
        raise AuthenticationError("Missing authentication credentials")

    token = credentials.credentials

    # Check if it's an API token (starts with prefix)
    if token.startswith(settings.api_token_prefix):
        return await _validate_api_token(token, db)

    # Otherwise try to decode as JWT
    return await _validate_session_jwt(token, db)


async def _validate_api_token(token: str, db: AsyncSession) -> User:
    """Validate an API token and return the associated user."""
    token_hash = hash_token(token)

    result = await db.execute(
        select(ApiToken)
        .options(joinedload(ApiToken.user))
        .where(
            ApiToken.token_hash == token_hash,
            ApiToken.is_revoked == False,
            or_(
                ApiToken.expires_at == None,
                ApiToken.expires_at > datetime.now(timezone.utc),
            ),
        )
    )
    api_token = result.scalar_one_or_none()

    if api_token is None:
        raise AuthenticationError("Invalid or expired API token")

    if not api_token.user.is_active:
        raise AuthenticationError("User account is disabled")

    # Update last used timestamp
    api_token.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return api_token.user


async def _validate_session_jwt(token: str, db: AsyncSession) -> User:
    """Validate a session JWT and return the associated user."""
    payload = decode_session_jwt(token)

    if payload is None:
        raise AuthenticationError("Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Invalid token payload")

    result = await db.execute(
        select(User).where(
            User.id == UUID(user_id),
            User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found or inactive")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current user and verify they are active."""
    if not current_user.is_active:
        raise AuthenticationError("User account is disabled")
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Get current user and verify they have admin privileges."""
    if not current_user.is_admin:
        raise AuthorizationError("Admin privileges required")
    return current_user


async def rate_limit_user(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    redis: Redis = Depends(get_redis),
) -> User:
    """
    Apply rate limiting based on user's configured limits.

    Returns the user if within limits.
    Stores rate limit headers in request state for middleware to add.
    """
    headers = await check_rate_limit(
        redis=redis,
        user_id=str(current_user.id),
        rate_limit_per_second=current_user.rate_limit_per_second,
        rate_limit_burst=current_user.rate_limit_burst,
    )

    # Store headers in request state for middleware
    request.state.rate_limit_headers = headers

    return current_user
