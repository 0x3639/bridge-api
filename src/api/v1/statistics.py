from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.dependencies import get_db, get_redis, rate_limit_user
from src.models.network_stats import NetworkStats
from src.models.orchestrator import OrchestratorNode, OrchestratorSnapshot
from src.models.user import User
from src.schemas.statistics import (
    BridgeHealthOverTime,
    BridgeHealthResponse,
    NetworkAggregateStats,
    NetworkStatsResponse,
    UptimeResponse,
    UptimeStats,
)
from src.services.cache_service import CacheService

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("/bridge", response_model=BridgeHealthResponse)
async def get_bridge_health_history(
    hours: int = Query(24, ge=1, le=720, description="Hours of history to return"),
    interval_minutes: int = Query(
        60, ge=1, le=1440, description="Aggregation interval in minutes"
    ),
    _user: User = Depends(rate_limit_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> BridgeHealthResponse:
    """Get bridge health history over time."""
    cache = CacheService(redis)
    cache_key = f"stats:bridge:{hours}:{interval_minutes}"

    # Try cache first
    cached = await cache.get(cache_key)
    if cached:
        return BridgeHealthResponse(**cached)

    # Calculate time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    # Get total orchestrator count
    node_count_result = await db.execute(
        select(func.count()).where(OrchestratorNode.is_active == True)
    )
    total_count = node_count_result.scalar_one()

    # Aggregate snapshots by interval
    interval = timedelta(minutes=interval_minutes)
    data_points = []
    current_time = start_time
    online_counts = []

    while current_time < end_time:
        interval_end = current_time + interval

        # Count online orchestrators in this interval
        result = await db.execute(
            select(func.count(func.distinct(OrchestratorSnapshot.node_id))).where(
                OrchestratorSnapshot.timestamp >= current_time,
                OrchestratorSnapshot.timestamp < interval_end,
                OrchestratorSnapshot.is_online == True,
            )
        )
        online_count = result.scalar_one()

        is_bridge_online = online_count >= settings.min_online_for_bridge

        data_points.append(
            BridgeHealthOverTime(
                timestamp=current_time,
                online_count=online_count,
                total_count=total_count,
                is_bridge_online=is_bridge_online,
            )
        )

        online_counts.append(online_count)
        current_time = interval_end

    # Calculate statistics
    avg_online = sum(online_counts) / len(online_counts) if online_counts else 0
    min_online = min(online_counts) if online_counts else 0
    max_online = max(online_counts) if online_counts else 0

    response = BridgeHealthResponse(
        period_start=start_time,
        period_end=end_time,
        data_points=data_points,
        avg_online_count=round(avg_online, 2),
        min_online_count=min_online,
        max_online_count=max_online,
    )

    # Cache the result
    await cache.set(cache_key, response.model_dump(), ttl=settings.cache_stats_ttl)

    return response


@router.get("/networks", response_model=NetworkStatsResponse)
async def get_network_statistics(
    hours: int = Query(24, ge=1, le=720, description="Hours of history"),
    _user: User = Depends(rate_limit_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> NetworkStatsResponse:
    """Get aggregate network statistics (wraps/unwraps) over time."""
    cache = CacheService(redis)
    cache_key = f"stats:networks:{hours}"

    # Try cache first
    cached = await cache.get(cache_key)
    if cached:
        return NetworkStatsResponse(**cached)

    # Calculate time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    # Get latest snapshot for each node in the time range
    # and sum up the network stats
    networks = ["bnb", "eth", "supernova"]
    network_stats = []

    for network in networks:
        result = await db.execute(
            select(
                func.sum(NetworkStats.wraps_count).label("total_wraps"),
                func.sum(NetworkStats.unwraps_count).label("total_unwraps"),
            )
            .join(OrchestratorSnapshot)
            .where(
                OrchestratorSnapshot.timestamp >= start_time,
                OrchestratorSnapshot.timestamp <= end_time,
                NetworkStats.network == network,
            )
        )
        row = result.one()

        network_stats.append(
            NetworkAggregateStats(
                network=network,
                total_wraps=row.total_wraps or 0,
                total_unwraps=row.total_unwraps or 0,
                period_start=start_time,
                period_end=end_time,
            )
        )

    response = NetworkStatsResponse(
        period_start=start_time,
        period_end=end_time,
        networks=network_stats,
    )

    # Cache the result
    await cache.set(cache_key, response.model_dump(), ttl=settings.cache_stats_ttl)

    return response


@router.get("/uptime", response_model=UptimeResponse)
async def get_uptime_statistics(
    hours: int = Query(24, ge=1, le=720, description="Hours of history"),
    _user: User = Depends(rate_limit_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> UptimeResponse:
    """Get uptime statistics for each orchestrator and the bridge overall."""
    cache = CacheService(redis)
    cache_key = f"stats:uptime:{hours}"

    # Try cache first
    cached = await cache.get(cache_key)
    if cached:
        return UptimeResponse(**cached)

    # Calculate time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    # Single aggregated query to get all node stats - fixes N+1 query issue
    # Previously: 1 + 2N queries (2 per node). Now: 2 queries total.
    uptime_stats_result = await db.execute(
        select(
            OrchestratorSnapshot.node_id,
            OrchestratorNode.name.label("node_name"),
            func.count().label("total_snapshots"),
            func.sum(
                func.cast(OrchestratorSnapshot.is_online, Integer)
            ).label("online_snapshots"),
        )
        .join(OrchestratorNode, OrchestratorSnapshot.node_id == OrchestratorNode.id)
        .where(
            OrchestratorNode.is_active == True,
            OrchestratorSnapshot.timestamp >= start_time,
            OrchestratorSnapshot.timestamp <= end_time,
        )
        .group_by(OrchestratorSnapshot.node_id, OrchestratorNode.name)
    )
    stats_rows = uptime_stats_result.all()

    node_uptimes = []
    total_snapshots = 0
    total_online = 0

    for row in stats_rows:
        node_total = row.total_snapshots
        node_online = row.online_snapshots or 0
        uptime_pct = (node_online / node_total * 100) if node_total > 0 else 0

        node_uptimes.append(
            UptimeStats(
                node_id=row.node_id,
                node_name=row.node_name,
                period_start=start_time,
                period_end=end_time,
                total_snapshots=node_total,
                online_snapshots=node_online,
                uptime_percentage=round(uptime_pct, 2),
            )
        )

        total_snapshots += node_total
        total_online += node_online

    # Calculate bridge uptime (percentage of time with >= min_online orchestrators)
    # This is an approximation based on average online count
    bridge_uptime_pct = (total_online / total_snapshots * 100) if total_snapshots > 0 else 0

    response = UptimeResponse(
        period_start=start_time,
        period_end=end_time,
        bridge_uptime_percentage=round(bridge_uptime_pct, 2),
        node_uptimes=node_uptimes,
    )

    # Cache the result
    await cache.set(cache_key, response.model_dump(), ttl=settings.cache_stats_ttl)

    return response
