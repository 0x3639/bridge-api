"""
Orchestrator service for managing node data collection and status.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import settings
from src.models.network_stats import NetworkStats
from src.models.orchestrator import OrchestratorNode, OrchestratorSnapshot
from src.services.cache_service import CacheService
from src.utils.rpc_client import RPCClient

logger = logging.getLogger(__name__)


class OrchestratorService:
    """Service for orchestrator data collection and management."""

    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache = CacheService(redis)
        self.rpc_client = RPCClient()

    async def get_all_nodes(self, active_only: bool = True) -> list[OrchestratorNode]:
        """Get all orchestrator nodes."""
        query = select(OrchestratorNode)
        if active_only:
            query = query.where(OrchestratorNode.is_active == True)
        query = query.order_by(OrchestratorNode.name)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_node_by_id(self, node_id: int) -> Optional[OrchestratorNode]:
        """Get a single orchestrator node by ID."""
        result = await self.db.execute(
            select(OrchestratorNode).where(OrchestratorNode.id == node_id)
        )
        return result.scalar_one_or_none()

    async def collect_all_status(self) -> dict:
        """
        Collect status from all active orchestrator nodes.

        Returns:
            Summary of collection results
        """
        nodes = await self.get_all_nodes(active_only=True)

        if not nodes:
            logger.warning("No active orchestrator nodes configured")
            return {"collected": 0, "online": 0, "total": 0}

        # Limit concurrent requests - use 5 to avoid rate limiting
        # Each query makes 2 requests (getIdentity + getStatus), so 5 concurrent = 10 requests
        semaphore = asyncio.Semaphore(5)

        async def query_with_limit(node):
            async with semaphore:
                return await self.rpc_client.query_orchestrator(
                    ip=str(node.ip_address),
                    port=node.rpc_port,
                    node_name=node.name,
                )

        # Collect from all nodes with limited concurrency
        tasks = [query_with_limit(node) for node in nodes]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process and save results
        online_count = 0
        for node, result in zip(nodes, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to query node {node.name}: {result}")
                result = {
                    "ip": str(node.ip_address),
                    "node_name": node.name,
                    "pillar_name": None,
                    "producer_address": None,
                    "state": None,
                    "state_name": None,
                    "is_online": False,
                    "response_time_ms": None,
                    "error_message": str(result),
                    "network_stats": [],
                    "raw_identity": None,
                    "raw_status": None,
                    "timestamp": datetime.now(timezone.utc),
                }

            # Create snapshot
            snapshot = OrchestratorSnapshot(
                node_id=node.id,
                timestamp=result["timestamp"],
                pillar_name=result["pillar_name"],
                producer_address=result["producer_address"],
                state=result["state"],
                state_name=result["state_name"],
                is_online=result["is_online"],
                response_time_ms=result["response_time_ms"],
                error_message=result["error_message"],
                raw_identity=result["raw_identity"],
                raw_status=result["raw_status"],
            )
            self.db.add(snapshot)
            await self.db.flush()  # Get the snapshot ID

            # Add network stats
            for ns in result.get("network_stats", []):
                network_stat = NetworkStats(
                    snapshot_id=snapshot.id,
                    network=ns["network"],
                    wraps_count=ns["wraps_count"],
                    unwraps_count=ns["unwraps_count"],
                )
                self.db.add(network_stat)

            if result["is_online"]:
                online_count += 1

        await self.db.commit()

        # Update cache with latest status
        await self._update_status_cache()

        summary = {
            "collected": len(nodes),
            "online": online_count,
            "total": len(nodes),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"Collected status: {online_count}/{len(nodes)} orchestrators online"
        )

        return summary

    async def get_current_status(self) -> dict:
        """
        Get current status of all orchestrators.

        Returns cached data if available, otherwise queries the database.
        """
        # Try cache first
        cached = await self.cache.get("status:current")
        if cached:
            return cached

        # Query database for latest snapshots
        return await self._build_current_status()

    async def _build_current_status(self) -> dict:
        """Build current status from latest snapshots in database."""
        nodes = await self.get_all_nodes(active_only=True)

        # Single query to get latest snapshot for each node - fixes N+1 query issue
        # Previously: 1 query per node. Now: 1 query total (+ 1 for network stats).
        # Uses a subquery to get max timestamp per node, then joins to get full snapshot
        latest_timestamps_subq = (
            select(
                OrchestratorSnapshot.node_id,
                func.max(OrchestratorSnapshot.timestamp).label("max_timestamp"),
            )
            .group_by(OrchestratorSnapshot.node_id)
            .subquery()
        )

        latest_snapshots_result = await self.db.execute(
            select(OrchestratorSnapshot)
            .options(selectinload(OrchestratorSnapshot.network_stats))
            .join(
                latest_timestamps_subq,
                (OrchestratorSnapshot.node_id == latest_timestamps_subq.c.node_id)
                & (OrchestratorSnapshot.timestamp == latest_timestamps_subq.c.max_timestamp),
            )
        )
        latest_snapshots = {s.node_id: s for s in latest_snapshots_result.scalars().all()}

        orchestrators = []
        online_count = 0

        for node in nodes:
            snapshot = latest_snapshots.get(node.id)

            if snapshot:
                network_stats = [
                    {
                        "network": ns.network,
                        "wraps_count": ns.wraps_count,
                        "unwraps_count": ns.unwraps_count,
                    }
                    for ns in snapshot.network_stats
                ]

                orchestrators.append(
                    {
                        "node_id": node.id,
                        "node_name": node.name,
                        "ip_address": str(node.ip_address),
                        "pillar_name": snapshot.pillar_name,
                        "producer_address": snapshot.producer_address,
                        "state": snapshot.state,
                        "state_name": snapshot.state_name,
                        "is_online": snapshot.is_online,
                        "response_time_ms": snapshot.response_time_ms,
                        "error_message": snapshot.error_message,
                        "network_stats": network_stats,
                        "last_checked": snapshot.timestamp.isoformat(),
                    }
                )

                if snapshot.is_online:
                    online_count += 1
            else:
                # No snapshot yet
                orchestrators.append(
                    {
                        "node_id": node.id,
                        "node_name": node.name,
                        "ip_address": str(node.ip_address),
                        "pillar_name": None,
                        "producer_address": None,
                        "state": None,
                        "state_name": None,
                        "is_online": False,
                        "response_time_ms": None,
                        "error_message": "No data collected yet",
                        "network_stats": [],
                        "last_checked": None,
                    }
                )

        # Determine bridge status
        bridge_status = (
            "online" if online_count >= settings.min_online_for_bridge else "offline"
        )

        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bridge_status": bridge_status,
            "online_count": online_count,
            "total_count": len(nodes),
            "min_required": settings.min_online_for_bridge,
            "orchestrators": orchestrators,
        }

        return status

    async def _update_status_cache(self) -> None:
        """Update the status cache with latest data."""
        status = await self._build_current_status()
        await self.cache.set("status:current", status, ttl=settings.cache_status_ttl)

    async def get_node_history(
        self,
        node_id: int,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> tuple[list[dict], int]:
        """
        Get historical snapshots for a node.

        Returns:
            Tuple of (snapshots, total_count)
        """
        query = (
            select(OrchestratorSnapshot)
            .options(selectinload(OrchestratorSnapshot.network_stats))
            .where(OrchestratorSnapshot.node_id == node_id)
        )

        if start_time:
            query = query.where(OrchestratorSnapshot.timestamp >= start_time)
        if end_time:
            query = query.where(OrchestratorSnapshot.timestamp <= end_time)

        # Get total count
        from sqlalchemy import func

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get paginated results
        query = query.order_by(OrchestratorSnapshot.timestamp.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        snapshots = result.scalars().all()

        history = []
        for snapshot in snapshots:
            network_stats = [
                {
                    "network": ns.network,
                    "wraps_count": ns.wraps_count,
                    "unwraps_count": ns.unwraps_count,
                }
                for ns in snapshot.network_stats
            ]

            history.append(
                {
                    "id": snapshot.id,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "pillar_name": snapshot.pillar_name,
                    "producer_address": snapshot.producer_address,
                    "state": snapshot.state,
                    "state_name": snapshot.state_name,
                    "is_online": snapshot.is_online,
                    "response_time_ms": snapshot.response_time_ms,
                    "error_message": snapshot.error_message,
                    "network_stats": network_stats,
                }
            )

        return history, total

    async def close(self) -> None:
        """Close the RPC client."""
        await self.rpc_client.close()
