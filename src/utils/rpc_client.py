"""
Async JSON-RPC client for querying orchestrator nodes.
Ported from the original sync implementation to use httpx async.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

# State mapping
STATE_MAP = {
    0: "LiveState",
    1: "KeyGenState",
    2: "HaltedState",
    3: "EmergencyState",
    4: "ReSignState",
}

# States that indicate orchestrator is online
ONLINE_STATES = [0, 1]


class RPCClient:
    """Async JSON-RPC client for orchestrator communication."""

    def __init__(
        self,
        timeout: int = None,
        max_retries: int = 3,
        retry_delay: float = 0.3,
    ):
        """
        Initialize the RPC client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (exponential backoff)
        """
        self.timeout = timeout or settings.orchestrator_rpc_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def _make_request(
        self,
        ip: str,
        port: int,
        method: str,
        params: list = None,
    ) -> dict:
        """
        Make a JSON-RPC request (no retries to avoid rate limiting).

        Args:
            ip: IP address of the orchestrator
            port: RPC port
            method: RPC method to call
            params: Method parameters

        Returns:
            Response data dictionary

        Raises:
            Exception on failure
        """
        url = f"http://{ip}:{port}"
        payload = {"method": method, "params": params or []}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    async def query_orchestrator(
        self,
        ip: str,
        port: int = None,
        node_name: str = "Unknown",
    ) -> dict:
        """
        Query a single orchestrator for its identity and status.

        Args:
            ip: IP address of the orchestrator
            port: RPC port (defaults to settings)
            node_name: Name of the node for error reporting

        Returns:
            Dictionary containing orchestrator status information
        """
        port = port or settings.orchestrator_rpc_port
        start_time = time.time()

        try:
            # Query identity
            identity_data = await self._make_request(ip, port, "getIdentity")

            # Wait 1 second between queries for a single node to avoid rate limiting
            await asyncio.sleep(1.0)

            # Query status
            status_data = await self._make_request(ip, port, "getStatus")

            response_time_ms = int((time.time() - start_time) * 1000)

            # Check for RPC errors
            if identity_data.get("error") or status_data.get("error"):
                error_msg = identity_data.get("error") or status_data.get("error")
                logger.error(f"RPC error for {ip}: {error_msg}")
                return self._create_error_response(
                    ip, node_name, str(error_msg), response_time_ms
                )

            # Process the data
            return self._process_response(
                ip, node_name, identity_data, status_data, response_time_ms
            )

        except httpx.RequestError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Network error querying orchestrator at {ip}: {str(e)}")
            return self._create_error_response(
                ip, node_name, f"Network error: {str(e)}", response_time_ms
            )
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Unexpected error querying orchestrator at {ip}: {str(e)}")
            return self._create_error_response(
                ip, node_name, f"Error: {str(e)}", response_time_ms
            )

    def _process_response(
        self,
        ip: str,
        node_name: str,
        identity_data: dict,
        status_data: dict,
        response_time_ms: int,
    ) -> dict:
        """Process raw orchestrator data into standardized format."""
        result_identity = identity_data.get("result", {})
        result_status = status_data.get("result", {})

        pillar_name = result_identity.get("pillarName", "Unknown")
        producer_address = result_identity.get("producer", "Unknown")
        state_num = result_status.get("state")
        state_name = STATE_MAP.get(state_num, "Unknown")
        is_online = state_num in ONLINE_STATES

        # Process network statistics
        network_stats = self._process_network_stats(result_status)

        return {
            "ip": ip,
            "node_name": node_name,
            "pillar_name": pillar_name,
            "producer_address": producer_address,
            "state": state_num,
            "state_name": state_name,
            "is_online": is_online,
            "response_time_ms": response_time_ms,
            "error_message": None,
            "network_stats": network_stats,
            "raw_identity": result_identity,
            "raw_status": result_status,
            "timestamp": datetime.now(timezone.utc),
        }

    def _process_network_stats(self, status_result: dict) -> list[dict]:
        """Extract network statistics from status data."""
        network_stats = []

        network_mapping = {
            "BNB Chain": "bnb",
            "Ethereum": "eth",
            "Supernova": "supernova",
        }

        networks = status_result.get("networks", {})

        for api_name, db_name in network_mapping.items():
            network_data = networks.get(api_name, {})
            network_stats.append(
                {
                    "network": db_name,
                    "wraps_count": network_data.get("wrapsToSign", 0),
                    "unwraps_count": network_data.get("unwrapsToSign", 0),
                }
            )

        return network_stats

    def _create_error_response(
        self,
        ip: str,
        node_name: str,
        error: str,
        response_time_ms: int,
    ) -> dict:
        """Create a standardized error response."""
        return {
            "ip": ip,
            "node_name": node_name,
            "pillar_name": None,
            "producer_address": None,
            "state": None,
            "state_name": None,
            "is_online": False,
            "response_time_ms": response_time_ms,
            "error_message": error,
            "network_stats": [
                {"network": "bnb", "wraps_count": 0, "unwraps_count": 0},
                {"network": "eth", "wraps_count": 0, "unwraps_count": 0},
                {"network": "supernova", "wraps_count": 0, "unwraps_count": 0},
            ],
            "raw_identity": None,
            "raw_status": None,
            "timestamp": datetime.now(timezone.utc),
        }

    async def close(self) -> None:
        """Close the RPC client. No-op since we create new clients per request."""
        pass
