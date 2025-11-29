"""
Tests for orchestrator endpoints.
"""
import pytest
from httpx import AsyncClient

from src.models.orchestrator import OrchestratorNode
from tests.conftest import auth_headers


class TestOrchestratorList:
    """Tests for listing orchestrator nodes."""

    @pytest.mark.asyncio
    async def test_list_orchestrators(
        self,
        client: AsyncClient,
        test_api_token,
        test_orchestrator_node: OrchestratorNode,
    ):
        """Test listing all orchestrator nodes."""
        token, _ = test_api_token

        response = await client.get(
            "/api/v1/orchestrators",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_orchestrators_unauthorized(self, client: AsyncClient):
        """Test listing orchestrators without auth."""
        response = await client.get("/api/v1/orchestrators")

        assert response.status_code == 401


class TestOrchestratorStatus:
    """Tests for orchestrator status endpoints."""

    @pytest.mark.asyncio
    async def test_get_status(
        self,
        client: AsyncClient,
        test_api_token,
        test_orchestrator_node: OrchestratorNode,
    ):
        """Test getting current orchestrator status."""
        token, _ = test_api_token

        response = await client.get(
            "/api/v1/orchestrators/status",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert "bridge_status" in data
        assert "online_count" in data
        assert "total_count" in data
        assert "min_required" in data
        assert "orchestrators" in data

    @pytest.mark.asyncio
    async def test_get_status_summary(
        self,
        client: AsyncClient,
        test_api_token,
    ):
        """Test getting status summary only."""
        token, _ = test_api_token

        response = await client.get(
            "/api/v1/orchestrators/status/summary",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert "bridge_status" in data
        assert "online_count" in data
        assert "total_count" in data
        # Summary should not include full orchestrator list
        assert "orchestrators" not in data or data.get("orchestrators") is None


class TestOrchestratorDetail:
    """Tests for individual orchestrator endpoints."""

    @pytest.mark.asyncio
    async def test_get_orchestrator(
        self,
        client: AsyncClient,
        test_api_token,
        test_orchestrator_node: OrchestratorNode,
    ):
        """Test getting a single orchestrator."""
        token, _ = test_api_token

        response = await client.get(
            f"/api/v1/orchestrators/{test_orchestrator_node.id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert test_orchestrator_node.name in data["name"]
        assert data["ip_address"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_get_orchestrator_not_found(
        self,
        client: AsyncClient,
        test_api_token,
    ):
        """Test getting a non-existent orchestrator."""
        token, _ = test_api_token

        response = await client.get(
            "/api/v1/orchestrators/99999",
            headers=auth_headers(token),
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_orchestrator_history(
        self,
        client: AsyncClient,
        test_api_token,
        test_orchestrator_node: OrchestratorNode,
    ):
        """Test getting orchestrator history."""
        token, _ = test_api_token

        response = await client.get(
            f"/api/v1/orchestrators/{test_orchestrator_node.id}/history",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert "snapshots" in data
        assert isinstance(data["snapshots"], list)
