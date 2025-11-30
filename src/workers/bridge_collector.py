"""
Bridge data collector - Standalone worker for syncing wrap/unwrap token requests.

This runs as a separate process from the main API to ensure complete isolation.
It has its own dedicated database connection pool and does not impact API performance.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.dependencies import BRIDGE_SYNC_COMPLETE_KEY
from src.models.bridge import UnwrapTokenRequest, WrapTokenRequest
from src.utils.bridge_rpc_client import BridgeRPCClient

logger = logging.getLogger(__name__)


class BridgeCollector:
    """
    Collector for bridge wrap/unwrap token requests.

    Uses a dedicated database connection pool (separate from API) to avoid
    competing for connections with API requests.
    """

    def __init__(self):
        # Create dedicated database engine with small pool for worker
        self.engine = create_async_engine(
            settings.database_url,
            pool_size=settings.bridge_db_pool_size,
            max_overflow=settings.bridge_db_max_overflow,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=True,
        )
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.rpc_client = BridgeRPCClient()
        self.redis: Optional[Redis] = None

    async def _init_redis(self) -> None:
        """Initialize Redis connection."""
        if self.redis is None:
            self.redis = Redis.from_url(settings.redis_url, decode_responses=True)

    async def _close_redis(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            self.redis = None

    async def run(self) -> None:
        """
        Main loop - runs initial sync then polls for new data every minute.
        """
        logger.info("Bridge collector starting...")
        await self._init_redis()

        try:
            # Check if initial sync is needed
            await self.initial_sync()

            # Main polling loop
            while True:
                await asyncio.sleep(settings.bridge_poll_interval)
                try:
                    await self.collect_new_data()
                except Exception as e:
                    logger.error(f"Error collecting new bridge data: {e}")
        finally:
            await self._close_redis()
            await self.rpc_client.close()
            await self.engine.dispose()

    async def initial_sync(self) -> None:
        """
        Perform initial sync if tables are empty.
        """
        async with self.session_maker() as session:
            wrap_count = await self._get_db_wrap_count(session)
            unwrap_count = await self._get_db_unwrap_count(session)

            if wrap_count == 0 and unwrap_count == 0:
                logger.info("Tables empty, performing full initial sync...")
                await self._full_sync_wrap_requests(session)
                await self._full_sync_unwrap_requests(session)
                logger.info("Initial sync complete")
            else:
                logger.info(
                    f"Tables already populated (wraps={wrap_count}, unwraps={unwrap_count}), "
                    "skipping full sync"
                )

            # Set sync complete flag in Redis
            await self._set_sync_complete()

    async def collect_new_data(self) -> None:
        """
        Collect new data since last sync.
        Fetches recent pages and stops when hitting existing records.
        """
        async with self.session_maker() as session:
            await self._sync_new_wrap_requests(session)
            await self._sync_new_unwrap_requests(session)

    async def _full_sync_wrap_requests(self, session: AsyncSession) -> None:
        """Paginate through all wrap requests and insert them."""
        logger.info("Starting full sync of wrap requests...")

        # Get total count first
        total = await self.rpc_client.get_wrap_count()
        logger.info(f"Total wrap requests to sync: {total}")

        page_size = settings.bridge_batch_size
        page = 0
        synced = 0

        while synced < total:
            try:
                result = await self.rpc_client.get_all_wrap_requests(
                    page_index=page, page_size=page_size
                )
                records = result.get("list", [])

                if not records:
                    break

                await self._upsert_wrap_requests(session, records)
                synced += len(records)
                page += 1

                logger.info(f"Synced wrap requests: {synced}/{total}")

            except Exception as e:
                logger.error(f"Error syncing wrap requests page {page}: {e}")
                raise

        logger.info(f"Full sync of wrap requests complete: {synced} records")

    async def _full_sync_unwrap_requests(self, session: AsyncSession) -> None:
        """Paginate through all unwrap requests and insert them."""
        logger.info("Starting full sync of unwrap requests...")

        # Get total count first
        total = await self.rpc_client.get_unwrap_count()
        logger.info(f"Total unwrap requests to sync: {total}")

        page_size = settings.bridge_batch_size
        page = 0
        synced = 0

        while synced < total:
            try:
                result = await self.rpc_client.get_all_unwrap_requests(
                    page_index=page, page_size=page_size
                )
                records = result.get("list", [])

                if not records:
                    break

                await self._upsert_unwrap_requests(session, records)
                synced += len(records)
                page += 1

                logger.info(f"Synced unwrap requests: {synced}/{total}")

            except Exception as e:
                logger.error(f"Error syncing unwrap requests page {page}: {e}")
                raise

        logger.info(f"Full sync of unwrap requests complete: {synced} records")

    async def _sync_new_wrap_requests(self, session: AsyncSession) -> None:
        """Sync new wrap requests and update pending ones.

        This method:
        1. Fetches new wrap requests (higher momentum height than DB)
        2. Updates confirmations_to_finality for pending requests (> 0)
        """
        # Get latest momentum height from DB
        latest_height = await self._get_latest_wrap_momentum_height(session)

        page = 0
        page_size = settings.bridge_batch_size
        new_count = 0

        while True:
            try:
                result = await self.rpc_client.get_all_wrap_requests(
                    page_index=page, page_size=page_size
                )
                records = result.get("list", [])

                if not records:
                    break

                # Filter to only new records (higher momentum height)
                if latest_height:
                    new_records = [
                        r for r in records
                        if r.get("creationMomentumHeight", 0) > latest_height
                    ]
                else:
                    new_records = records

                if new_records:
                    await self._upsert_wrap_requests(session, new_records)
                    new_count += len(new_records)

                # Stop if we've hit existing records
                if len(new_records) < len(records):
                    break

                page += 1

            except Exception as e:
                logger.error(f"Error syncing new wrap requests: {e}")
                break

        if new_count > 0:
            logger.info(f"Synced {new_count} new wrap requests")

        # Update pending wrap requests (confirmations_to_finality > 0)
        await self._update_pending_wrap_requests(session)

    async def _update_pending_wrap_requests(self, session: AsyncSession) -> None:
        """Update confirmations_to_finality for pending wrap requests.

        Fetches the latest data from RPC for all wrap requests that haven't
        been finalized yet (confirmations_to_finality > 0).
        """
        # Get all pending request IDs from DB
        result = await session.execute(
            select(WrapTokenRequest.request_id).where(
                WrapTokenRequest.confirmations_to_finality > 0
            )
        )
        pending_ids = {row[0] for row in result.fetchall()}

        if not pending_ids:
            return

        logger.info(f"Updating {len(pending_ids)} pending wrap requests")

        # Fetch pages from RPC until we've checked all pending requests
        page = 0
        page_size = settings.bridge_batch_size
        updated_count = 0
        checked_ids = set()

        while checked_ids < pending_ids:
            try:
                result = await self.rpc_client.get_all_wrap_requests(
                    page_index=page, page_size=page_size
                )
                records = result.get("list", [])

                if not records:
                    break

                # Filter to only records we need to update
                pending_records = [
                    r for r in records
                    if r.get("id") in pending_ids
                ]

                if pending_records:
                    await self._upsert_wrap_requests(session, pending_records)
                    updated_count += len(pending_records)
                    checked_ids.update(r.get("id") for r in pending_records)

                page += 1

                # Safety limit - don't paginate forever
                if page > 100:
                    logger.warning("Hit page limit while updating pending wrap requests")
                    break

            except Exception as e:
                logger.error(f"Error updating pending wrap requests: {e}")
                break

        if updated_count > 0:
            logger.info(f"Updated {updated_count} pending wrap requests")

    async def _sync_new_unwrap_requests(self, session: AsyncSession) -> None:
        """Sync new unwrap requests and update pending ones.

        This method:
        1. Fetches new unwrap requests (higher momentum height than DB)
        2. Updates status for pending requests (not redeemed and not revoked)
        """
        # Get latest momentum height from DB
        latest_height = await self._get_latest_unwrap_momentum_height(session)

        page = 0
        page_size = settings.bridge_batch_size
        new_count = 0

        while True:
            try:
                result = await self.rpc_client.get_all_unwrap_requests(
                    page_index=page, page_size=page_size
                )
                records = result.get("list", [])

                if not records:
                    break

                # Filter to only new records (higher momentum height)
                if latest_height:
                    new_records = [
                        r for r in records
                        if r.get("registrationMomentumHeight", 0) > latest_height
                    ]
                else:
                    new_records = records

                if new_records:
                    await self._upsert_unwrap_requests(session, new_records)
                    new_count += len(new_records)

                # Stop if we've hit existing records
                if len(new_records) < len(records):
                    break

                page += 1

            except Exception as e:
                logger.error(f"Error syncing new unwrap requests: {e}")
                break

        if new_count > 0:
            logger.info(f"Synced {new_count} new unwrap requests")

        # Update pending unwrap requests (not redeemed and not revoked)
        await self._update_pending_unwrap_requests(session)

    async def _update_pending_unwrap_requests(self, session: AsyncSession) -> None:
        """Update status for pending unwrap requests.

        Fetches the latest data from RPC for all unwrap requests that haven't
        been redeemed or revoked yet. This updates:
        - redeemable_in: countdown until redeemable
        - redeemed: true when user redeems
        - revoked: true if revoked
        """
        # Get all pending unwrap identifiers from DB (tx_hash + log_index)
        result = await session.execute(
            select(
                UnwrapTokenRequest.transaction_hash,
                UnwrapTokenRequest.log_index
            ).where(
                UnwrapTokenRequest.redeemed == False,  # noqa: E712
                UnwrapTokenRequest.revoked == False,   # noqa: E712
            )
        )
        pending_keys = {(row[0], row[1]) for row in result.fetchall()}

        if not pending_keys:
            return

        logger.info(f"Updating {len(pending_keys)} pending unwrap requests")

        # Fetch pages from RPC until we've checked all pending requests
        page = 0
        page_size = settings.bridge_batch_size
        updated_count = 0
        checked_keys = set()

        while checked_keys < pending_keys:
            try:
                result = await self.rpc_client.get_all_unwrap_requests(
                    page_index=page, page_size=page_size
                )
                records = result.get("list", [])

                if not records:
                    break

                # Filter to only records we need to update
                pending_records = [
                    r for r in records
                    if (r.get("transactionHash"), r.get("logIndex")) in pending_keys
                ]

                if pending_records:
                    await self._upsert_unwrap_requests(session, pending_records)
                    updated_count += len(pending_records)
                    checked_keys.update(
                        (r.get("transactionHash"), r.get("logIndex"))
                        for r in pending_records
                    )

                page += 1

                # Safety limit - don't paginate forever
                if page > 100:
                    logger.warning("Hit page limit while updating pending unwrap requests")
                    break

            except Exception as e:
                logger.error(f"Error updating pending unwrap requests: {e}")
                break

        if updated_count > 0:
            logger.info(f"Updated {updated_count} pending unwrap requests")

    async def _upsert_wrap_requests(
        self, session: AsyncSession, records: List[Dict[str, Any]]
    ) -> None:
        """Insert or update wrap requests.

        Uses upsert to update confirmations_to_finality for existing records,
        as this value changes over time until the transaction is finalized.
        """
        if not records:
            return

        values = []
        for r in records:
            token = r.get("token", {})
            values.append({
                "request_id": r["id"],
                "network_class": r["networkClass"],
                "chain_id": r["chainId"],
                "to_address": r["toAddress"],
                "token_standard": r["tokenStandard"],
                "token_address": r["tokenAddress"],
                "token_symbol": token.get("symbol", "UNKNOWN"),
                "token_decimals": token.get("decimals", 8),
                "amount": Decimal(r["amount"]),
                "fee": Decimal(r["fee"]),
                "signature": r["signature"],
                "creation_momentum_height": r["creationMomentumHeight"],
                "confirmations_to_finality": r["confirmationsToFinality"],
            })

        stmt = insert(WrapTokenRequest).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["request_id"],
            set_={"confirmations_to_finality": stmt.excluded.confirmations_to_finality}
        )
        await session.execute(stmt)
        await session.commit()

    async def _upsert_unwrap_requests(
        self, session: AsyncSession, records: List[Dict[str, Any]]
    ) -> None:
        """Insert or update unwrap requests.

        Uses upsert to update dynamic fields for existing records:
        - redeemed: changes to true when user redeems
        - revoked: changes to true if revoked
        - redeemable_in: decreases over time until 0
        """
        if not records:
            return

        values = []
        for r in records:
            token = r.get("token", {})
            values.append({
                "transaction_hash": r["transactionHash"],
                "log_index": r["logIndex"],
                "registration_momentum_height": r["registrationMomentumHeight"],
                "network_class": r["networkClass"],
                "chain_id": r["chainId"],
                "to_address": r["toAddress"],
                "token_address": r["tokenAddress"],
                "token_standard": r["tokenStandard"],
                "token_symbol": token.get("symbol", "UNKNOWN"),
                "token_decimals": token.get("decimals", 8),
                "amount": Decimal(r["amount"]),
                "signature": r["signature"],
                "redeemed": r["redeemed"] == 1,
                "revoked": r["revoked"] == 1,
                "redeemable_in": r["redeemableIn"],
            })

        stmt = insert(UnwrapTokenRequest).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_unwrap_tx_log",
            set_={
                "redeemed": stmt.excluded.redeemed,
                "revoked": stmt.excluded.revoked,
                "redeemable_in": stmt.excluded.redeemable_in,
            }
        )
        await session.execute(stmt)
        await session.commit()

    async def _get_db_wrap_count(self, session: AsyncSession) -> int:
        """Get current count of wrap requests in DB."""
        result = await session.execute(
            select(func.count()).select_from(WrapTokenRequest)
        )
        return result.scalar_one()

    async def _get_db_unwrap_count(self, session: AsyncSession) -> int:
        """Get current count of unwrap requests in DB."""
        result = await session.execute(
            select(func.count()).select_from(UnwrapTokenRequest)
        )
        return result.scalar_one()

    async def _get_latest_wrap_momentum_height(
        self, session: AsyncSession
    ) -> Optional[int]:
        """Get the highest creation_momentum_height in DB."""
        result = await session.execute(
            select(func.max(WrapTokenRequest.creation_momentum_height))
        )
        return result.scalar_one_or_none()

    async def _get_latest_unwrap_momentum_height(
        self, session: AsyncSession
    ) -> Optional[int]:
        """Get the highest registration_momentum_height in DB."""
        result = await session.execute(
            select(func.max(UnwrapTokenRequest.registration_momentum_height))
        )
        return result.scalar_one_or_none()

    async def _set_sync_complete(self) -> None:
        """Set the Redis flag indicating sync is complete."""
        if self.redis:
            await self.redis.set(BRIDGE_SYNC_COMPLETE_KEY, "1")
            logger.info("Bridge sync complete flag set")
