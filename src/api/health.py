from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db, get_redis

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Basic health check response."""

    status: str
    service: str


class ReadinessResponse(BaseModel):
    """Readiness check response with component status."""

    status: str
    database: str
    redis: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint."""
    return HealthResponse(status="healthy", service="orchestrator-api")


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ReadinessResponse:
    """
    Readiness check that verifies database and Redis connections.

    Returns 200 if all components are ready, 503 otherwise.
    """
    db_status = "healthy"
    redis_status = "healthy"
    overall_status = "ready"

    # Check database
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
        overall_status = "not_ready"

    # Check Redis
    try:
        await redis.ping()
    except Exception:
        redis_status = "unhealthy"
        overall_status = "not_ready"

    return ReadinessResponse(
        status=overall_status,
        database=db_status,
        redis=redis_status,
    )
