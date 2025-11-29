"""
Tests for health check endpoints.
"""
import pytest
from httpx import AsyncClient


class TestHealth:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test basic health check endpoint."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data

    @pytest.mark.asyncio
    async def test_readiness_check(self, client: AsyncClient):
        """Test readiness check endpoint."""
        response = await client.get("/health/ready")

        # May be 200 or 503 depending on DB/Redis state in tests
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data


class TestRoot:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns API info."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data
