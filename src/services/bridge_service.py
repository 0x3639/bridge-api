"""
Bridge service for querying wrap/unwrap token requests.
"""
import logging
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bridge import UnwrapTokenRequest, WrapTokenRequest
from src.schemas.bridge import (
    UnwrapTokenListResponse,
    UnwrapTokenResponse,
    WrapTokenListResponse,
    WrapTokenResponse,
)
from src.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class BridgeService:
    """Service for bridge wrap/unwrap token request queries."""

    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache = CacheService(redis)

    async def get_wrap_requests(
        self,
        page: int = 0,
        page_size: int = 50,
        chain_id: Optional[int] = None,
        token_standard: Optional[str] = None,
        token_symbol: Optional[str] = None,
        to_address: Optional[str] = None,
    ) -> WrapTokenListResponse:
        """
        Get paginated wrap token requests with optional filters.

        Args:
            page: Page number (0-indexed)
            page_size: Number of records per page
            chain_id: Filter by chain ID
            token_standard: Filter by token standard (e.g., zts1znn...)
            token_symbol: Filter by token symbol (e.g., ZNN, QSR)
            to_address: Filter by destination Ethereum address

        Returns:
            Paginated list of wrap token requests
        """
        query = select(WrapTokenRequest)

        # Apply filters
        if chain_id is not None:
            query = query.where(WrapTokenRequest.chain_id == chain_id)
        if token_standard is not None:
            query = query.where(WrapTokenRequest.token_standard == token_standard)
        if token_symbol is not None:
            query = query.where(WrapTokenRequest.token_symbol == token_symbol)
        if to_address is not None:
            query = query.where(WrapTokenRequest.to_address == to_address)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar_one()

        # Get paginated results (sorted by creation_momentum_height DESC)
        query = query.order_by(WrapTokenRequest.creation_momentum_height.desc())
        query = query.offset(page * page_size).limit(page_size)

        result = await self.db.execute(query)
        records = result.scalars().all()

        items = [
            WrapTokenResponse(
                request_id=r.request_id,
                network_class=r.network_class,
                chain_id=r.chain_id,
                to_address=r.to_address,
                token_standard=r.token_standard,
                token_address=r.token_address,
                token_symbol=r.token_symbol,
                token_decimals=r.token_decimals,
                amount=str(r.amount),
                fee=str(r.fee),
                signature=r.signature,
                creation_momentum_height=r.creation_momentum_height,
                confirmations_to_finality=r.confirmations_to_finality,
                created_at=r.created_at,
            )
            for r in records
        ]

        return WrapTokenListResponse(
            count=total_count,
            page=page,
            page_size=page_size,
            items=items,
        )

    async def get_unwrap_requests(
        self,
        page: int = 0,
        page_size: int = 50,
        chain_id: Optional[int] = None,
        token_standard: Optional[str] = None,
        token_symbol: Optional[str] = None,
        to_address: Optional[str] = None,
        redeemed: Optional[bool] = None,
        revoked: Optional[bool] = None,
    ) -> UnwrapTokenListResponse:
        """
        Get paginated unwrap token requests with optional filters.

        Args:
            page: Page number (0-indexed)
            page_size: Number of records per page
            chain_id: Filter by chain ID
            token_standard: Filter by token standard
            token_symbol: Filter by token symbol
            to_address: Filter by destination Zenon address
            redeemed: Filter by redeemed status
            revoked: Filter by revoked status

        Returns:
            Paginated list of unwrap token requests
        """
        query = select(UnwrapTokenRequest)

        # Apply filters
        if chain_id is not None:
            query = query.where(UnwrapTokenRequest.chain_id == chain_id)
        if token_standard is not None:
            query = query.where(UnwrapTokenRequest.token_standard == token_standard)
        if token_symbol is not None:
            query = query.where(UnwrapTokenRequest.token_symbol == token_symbol)
        if to_address is not None:
            query = query.where(UnwrapTokenRequest.to_address == to_address)
        if redeemed is not None:
            query = query.where(UnwrapTokenRequest.redeemed == redeemed)
        if revoked is not None:
            query = query.where(UnwrapTokenRequest.revoked == revoked)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar_one()

        # Get paginated results (sorted by registration_momentum_height DESC)
        query = query.order_by(UnwrapTokenRequest.registration_momentum_height.desc())
        query = query.offset(page * page_size).limit(page_size)

        result = await self.db.execute(query)
        records = result.scalars().all()

        items = [
            UnwrapTokenResponse(
                transaction_hash=r.transaction_hash,
                log_index=r.log_index,
                registration_momentum_height=r.registration_momentum_height,
                network_class=r.network_class,
                chain_id=r.chain_id,
                to_address=r.to_address,
                token_address=r.token_address,
                token_standard=r.token_standard,
                token_symbol=r.token_symbol,
                token_decimals=r.token_decimals,
                amount=str(r.amount),
                signature=r.signature,
                redeemed=r.redeemed,
                revoked=r.revoked,
                redeemable_in=r.redeemable_in,
                created_at=r.created_at,
            )
            for r in records
        ]

        return UnwrapTokenListResponse(
            count=total_count,
            page=page,
            page_size=page_size,
            items=items,
        )

    async def get_wrap_count(self) -> int:
        """Get total count of wrap requests."""
        result = await self.db.execute(
            select(func.count()).select_from(WrapTokenRequest)
        )
        return result.scalar_one()

    async def get_unwrap_count(self) -> int:
        """Get total count of unwrap requests."""
        result = await self.db.execute(
            select(func.count()).select_from(UnwrapTokenRequest)
        )
        return result.scalar_one()
