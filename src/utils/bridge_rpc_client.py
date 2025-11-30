"""
Async JSON-RPC client for querying bridge wrap/unwrap token requests.
Uses the embedded.bridge RPC methods to fetch token requests.
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class BridgeRPCClient:
    """Async JSON-RPC client for bridge token request queries."""

    def __init__(
        self,
        url: str = None,
        timeout: int = None,
    ):
        """
        Initialize the Bridge RPC client.

        Args:
            url: RPC endpoint URL (defaults to settings.bridge_rpc_url)
            timeout: Request timeout in seconds (defaults to settings.bridge_rpc_timeout)
        """
        self.url = url or settings.bridge_rpc_url
        self.timeout = timeout or settings.bridge_rpc_timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._request_id = 0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0,
            )
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=limits,
            )
        return self._client

    def _next_request_id(self) -> int:
        """Generate the next request ID."""
        self._request_id += 1
        return self._request_id

    async def _make_request(
        self,
        method: str,
        params: List[Any] = None,
    ) -> Dict[str, Any]:
        """
        Make a JSON-RPC request to the bridge node.

        Args:
            method: RPC method to call
            params: Method parameters

        Returns:
            Response data dictionary

        Raises:
            httpx.RequestError: On network failure
            Exception: On RPC error
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": method,
            "params": params or [],
        }

        client = await self._get_client()
        response = await client.post(
            self.url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            error = data["error"]
            raise Exception(f"RPC error: {error.get('message', error)}")

        return data.get("result", {})

    async def get_all_wrap_requests(
        self,
        page_index: int = 0,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Fetch wrap token requests (Zenon -> Ethereum).

        Args:
            page_index: Page number (0-indexed)
            page_size: Number of records per page

        Returns:
            Dict with 'count' (total) and 'list' (records)
        """
        logger.debug(f"Fetching wrap requests: page={page_index}, size={page_size}")
        result = await self._make_request(
            "embedded.bridge.getAllWrapTokenRequests",
            [page_index, page_size],
        )
        return result

    async def get_all_unwrap_requests(
        self,
        page_index: int = 0,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Fetch unwrap token requests (Ethereum -> Zenon).

        Args:
            page_index: Page number (0-indexed)
            page_size: Number of records per page

        Returns:
            Dict with 'count' (total) and 'list' (records)
        """
        logger.debug(f"Fetching unwrap requests: page={page_index}, size={page_size}")
        result = await self._make_request(
            "embedded.bridge.getAllUnwrapTokenRequests",
            [page_index, page_size],
        )
        return result

    async def get_wrap_count(self) -> int:
        """
        Get the total count of wrap requests.

        Returns:
            Total number of wrap requests
        """
        result = await self.get_all_wrap_requests(page_index=0, page_size=1)
        return result.get("count", 0)

    async def get_unwrap_count(self) -> int:
        """
        Get the total count of unwrap requests.

        Returns:
            Total number of unwrap requests
        """
        result = await self.get_all_unwrap_requests(page_index=0, page_size=1)
        return result.get("count", 0)

    async def close(self) -> None:
        """Close the RPC client and release connection pool resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
