"""
Bridge API endpoints for wrap/unwrap token requests.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import (
    get_db,
    get_redis,
    rate_limit_user,
    require_bridge_sync_complete,
)
from src.models.user import User
from src.schemas.bridge import (
    BridgeSyncStatusResponse,
    UnwrapTokenListResponse,
    WrapTokenListResponse,
)
from src.services.bridge_service import BridgeService

router = APIRouter(prefix="/bridge", tags=["bridge"])


@router.get("/wraps", response_model=WrapTokenListResponse)
async def get_wrap_requests(
    page: int = Query(0, ge=0, description="Page number (0-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    chain_id: Optional[int] = Query(None, description="Filter by chain ID (e.g., 1 for Ethereum)"),
    token_standard: Optional[str] = Query(None, description="Filter by token standard (e.g., zts1znn...)"),
    token_symbol: Optional[str] = Query(None, description="Filter by token symbol (e.g., ZNN, QSR)"),
    to_address: Optional[str] = Query(None, description="Filter by destination Ethereum address"),
    confirmations_to_finality: Optional[int] = Query(None, ge=0, description="Filter by confirmations to finality (0 = finalized)"),
    _user: User = Depends(rate_limit_user),
    _sync_check: None = Depends(require_bridge_sync_complete),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> WrapTokenListResponse:
    """
    Get paginated wrap token requests (Zenon -> Ethereum).

    Wrap requests represent tokens being sent from Zenon Network to Ethereum.
    Results are sorted by creation_momentum_height in descending order (newest first).
    """
    service = BridgeService(db, redis)
    return await service.get_wrap_requests(
        page=page,
        page_size=page_size,
        chain_id=chain_id,
        token_standard=token_standard,
        token_symbol=token_symbol,
        to_address=to_address,
        confirmations_to_finality=confirmations_to_finality,
    )


@router.get("/unwraps", response_model=UnwrapTokenListResponse)
async def get_unwrap_requests(
    page: int = Query(0, ge=0, description="Page number (0-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    chain_id: Optional[int] = Query(None, description="Filter by chain ID (e.g., 1 for Ethereum)"),
    token_standard: Optional[str] = Query(None, description="Filter by token standard"),
    token_symbol: Optional[str] = Query(None, description="Filter by token symbol"),
    to_address: Optional[str] = Query(None, description="Filter by destination Zenon address"),
    redeemed: Optional[bool] = Query(None, description="Filter by redeemed status"),
    revoked: Optional[bool] = Query(None, description="Filter by revoked status"),
    _user: User = Depends(rate_limit_user),
    _sync_check: None = Depends(require_bridge_sync_complete),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> UnwrapTokenListResponse:
    """
    Get paginated unwrap token requests (Ethereum -> Zenon).

    Unwrap requests represent tokens being sent from Ethereum to Zenon Network.
    Results are sorted by registration_momentum_height in descending order (newest first).
    """
    service = BridgeService(db, redis)
    return await service.get_unwrap_requests(
        page=page,
        page_size=page_size,
        chain_id=chain_id,
        token_standard=token_standard,
        token_symbol=token_symbol,
        to_address=to_address,
        redeemed=redeemed,
        revoked=revoked,
    )


@router.get("/sync-status", response_model=BridgeSyncStatusResponse)
async def get_bridge_sync_status(
    _user: User = Depends(rate_limit_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> BridgeSyncStatusResponse:
    """
    Get the current status of bridge data synchronization.

    This endpoint does NOT require sync to be complete, so it can be used
    to check sync progress.
    """
    from src.dependencies import BRIDGE_SYNC_COMPLETE_KEY

    sync_complete = await redis.get(BRIDGE_SYNC_COMPLETE_KEY)

    service = BridgeService(db, redis)
    wrap_count = await service.get_wrap_count()
    unwrap_count = await service.get_unwrap_count()

    return BridgeSyncStatusResponse(
        sync_complete=bool(sync_complete),
        wrap_count=wrap_count,
        unwrap_count=unwrap_count,
    )
