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
        assert "health" in data
        # docs key is present when DOCS_ENABLED=true (default)
        assert "docs" in data


class TestDocs:
    """Tests for API documentation endpoints."""

    @pytest.mark.asyncio
    async def test_docs_endpoint_enabled(self, client: AsyncClient):
        """Test /docs is accessible when DOCS_ENABLED=true (default)."""
        response = await client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_redoc_endpoint_enabled(self, client: AsyncClient):
        """Test /redoc is accessible when DOCS_ENABLED=true (default)."""
        response = await client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_openapi_endpoint_enabled(self, client: AsyncClient):
        """Test OpenAPI JSON is accessible when DOCS_ENABLED=true (default)."""
        response = await client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
