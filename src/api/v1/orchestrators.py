from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.exceptions import NotFoundError
from src.dependencies import get_db, get_redis, rate_limit_user
from src.models.user import User
from src.services.orchestrator_service import OrchestratorService
from src.schemas.orchestrator import (
    BridgeStatusResponse,
    BridgeSummaryResponse,
    NetworkStatsResponse,
    OrchestratorHistoryListResponse,
    OrchestratorHistoryResponse,
    OrchestratorNodeListResponse,
    OrchestratorNodeResponse,
    OrchestratorStatusResponse,
)

router = APIRouter(prefix="/orchestrators", tags=["orchestrators"])


@router.get("", response_model=OrchestratorNodeListResponse)
async def list_orchestrator_nodes(
    active_only: bool = Query(True, description="Only return active nodes"),
    _user: User = Depends(rate_limit_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> OrchestratorNodeListResponse:
    """List all configured orchestrator nodes."""
    service = OrchestratorService(db, redis)
    nodes = await service.get_all_nodes(active_only=active_only)

    return OrchestratorNodeListResponse(
        nodes=[OrchestratorNodeResponse.model_validate(n) for n in nodes],
        total=len(nodes),
    )


@router.get("/status", response_model=BridgeStatusResponse)
async def get_bridge_status(
    _user: User = Depends(rate_limit_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> BridgeStatusResponse:
    """Get current status of all orchestrators and bridge health."""
    service = OrchestratorService(db, redis)
    status = await service.get_current_status()

    # Convert to response model
    orchestrators = []
    for o in status["orchestrators"]:
        network_stats = [
            NetworkStatsResponse(**ns) for ns in o.get("network_stats", [])
        ]
        orchestrators.append(
            OrchestratorStatusResponse(
                node_id=o["node_id"],
                node_name=o["node_name"],
                ip_address=o["ip_address"],
                pillar_name=o.get("pillar_name"),
                producer_address=o.get("producer_address"),
                state=o.get("state"),
                state_name=o.get("state_name"),
                is_online=o["is_online"],
                response_time_ms=o.get("response_time_ms"),
                error_message=o.get("error_message"),
                network_stats=network_stats,
                last_checked=datetime.fromisoformat(o["last_checked"])
                if o.get("last_checked")
                else datetime.now(),
            )
        )

    return BridgeStatusResponse(
        timestamp=datetime.fromisoformat(status["timestamp"]),
        bridge_status=status["bridge_status"],
        online_count=status["online_count"],
        total_count=status["total_count"],
        min_required=status["min_required"],
        orchestrators=orchestrators,
    )


@router.get("/status/summary", response_model=BridgeSummaryResponse)
async def get_bridge_status_summary(
    _user: User = Depends(rate_limit_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> BridgeSummaryResponse:
    """Get summary of bridge status without individual orchestrator details."""
    service = OrchestratorService(db, redis)
    status = await service.get_current_status()

    return BridgeSummaryResponse(
        timestamp=datetime.fromisoformat(status["timestamp"]),
        bridge_status=status["bridge_status"],
        online_count=status["online_count"],
        total_count=status["total_count"],
        min_required=status["min_required"],
    )


@router.get("/{node_id}", response_model=OrchestratorNodeResponse)
async def get_orchestrator_node(
    node_id: int,
    _user: User = Depends(rate_limit_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> OrchestratorNodeResponse:
    """Get details of a specific orchestrator node."""
    service = OrchestratorService(db, redis)
    node = await service.get_node_by_id(node_id)

    if node is None:
        raise NotFoundError("Orchestrator node not found")

    return OrchestratorNodeResponse.model_validate(node)


@router.get("/{node_id}/history", response_model=OrchestratorHistoryListResponse)
async def get_orchestrator_history(
    node_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    start_time: Optional[datetime] = Query(None, description="Start of time range"),
    end_time: Optional[datetime] = Query(None, description="End of time range"),
    _user: User = Depends(rate_limit_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> OrchestratorHistoryListResponse:
    """Get historical snapshots for an orchestrator node."""
    service = OrchestratorService(db, redis)

    # Verify node exists
    node = await service.get_node_by_id(node_id)
    if node is None:
        raise NotFoundError("Orchestrator node not found")

    # Calculate offset
    offset = (page - 1) * page_size

    history, total = await service.get_node_history(
        node_id=node_id,
        limit=page_size,
        offset=offset,
        start_time=start_time,
        end_time=end_time,
    )

    # Convert to response models
    snapshots = []
    for h in history:
        network_stats = [NetworkStatsResponse(**ns) for ns in h.get("network_stats", [])]
        snapshots.append(
            OrchestratorHistoryResponse(
                id=h["id"],
                timestamp=datetime.fromisoformat(h["timestamp"]),
                pillar_name=h.get("pillar_name"),
                producer_address=h.get("producer_address"),
                state=h.get("state"),
                state_name=h.get("state_name"),
                is_online=h["is_online"],
                response_time_ms=h.get("response_time_ms"),
                error_message=h.get("error_message"),
                network_stats=network_stats,
            )
        )

    return OrchestratorHistoryListResponse(
        node_id=node_id,
        node_name=node.name,
        snapshots=snapshots,
        total=total,
        page=page,
        page_size=page_size,
    )
