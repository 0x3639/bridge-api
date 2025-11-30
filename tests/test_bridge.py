"""
Tests for bridge wrap/unwrap token request endpoints.
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import BRIDGE_SYNC_COMPLETE_KEY
from src.models.bridge import UnwrapTokenRequest, WrapTokenRequest
from tests.conftest import auth_headers


@pytest.fixture
async def sample_wrap_requests(test_session: AsyncSession):
    """Create sample wrap token requests for testing."""
    requests = [
        WrapTokenRequest(
            request_id="abc123def456789012345678901234567890123456789012345678901234",
            network_class=2,
            chain_id=1,
            to_address="0x7405854156ffdfd0799849149ecf91e7f3fe64e6",
            token_standard="zts1znnxxxxxxxxxxxxx9z4ulx",
            token_address="0xb2e96a63479c2edd2fd62b382c89d5ca79f572d3",
            token_symbol="ZNN",
            token_decimals=8,
            amount=Decimal("100000000000"),
            fee=Decimal("3000000000"),
            signature="test_signature_1",
            creation_momentum_height=11919422,
            confirmations_to_finality=0,
        ),
        WrapTokenRequest(
            request_id="def456abc789012345678901234567890123456789012345678901234567",
            network_class=2,
            chain_id=1,
            to_address="0x5482a0937fc8ef7b6da95ec6c345800265b07e4b",
            token_standard="zts1qsrxxxxxxxxxxxxxmrhjll",
            token_address="0x96546afe4a21515a3a30cd3fd64a70eb478dc174",
            token_symbol="QSR",
            token_decimals=8,
            amount=Decimal("82253337192"),
            fee=Decimal("2467600115"),
            signature="test_signature_2",
            creation_momentum_height=11919421,
            confirmations_to_finality=0,
        ),
    ]
    for req in requests:
        test_session.add(req)
    await test_session.commit()
    return requests


@pytest.fixture
async def sample_unwrap_requests(test_session: AsyncSession):
    """Create sample unwrap token requests for testing."""
    requests = [
        UnwrapTokenRequest(
            transaction_hash="00149ed5a387f0d8abdb21bd20e334d6d3b046fca08081925f8e34fa3c13534d",
            log_index=74,
            registration_momentum_height=4543372,
            network_class=2,
            chain_id=1,
            to_address="z1qr9vtwsfr2n0nsxl2nfh6l5esqjh2wfj85cfq9",
            token_address="0xb2e96a63479c2edd2fd62b382c89d5ca79f572d3",
            token_standard="zts1znnxxxxxxxxxxxxx9z4ulx",
            token_symbol="ZNN",
            token_decimals=8,
            amount=Decimal("485000000"),
            signature="test_signature_1",
            redeemed=True,
            revoked=False,
            redeemable_in=0,
        ),
        UnwrapTokenRequest(
            transaction_hash="002c61dc008e2c15b9ee4473954c837594348b3a4e0f2f154cafd6e3aafd4cae",
            log_index=147,
            registration_momentum_height=5373145,
            network_class=2,
            chain_id=1,
            to_address="z1qp53j4f49te2ydtepjg9wkpxjp62k3qy4mgdwg",
            token_address="0xb2e96a63479c2edd2fd62b382c89d5ca79f572d3",
            token_standard="zts1znnxxxxxxxxxxxxx9z4ulx",
            token_symbol="ZNN",
            token_decimals=8,
            amount=Decimal("117100909711"),
            signature="test_signature_2",
            redeemed=True,
            revoked=False,
            redeemable_in=0,
        ),
        UnwrapTokenRequest(
            transaction_hash="003c61dc008e2c15b9ee4473954c837594348b3a4e0f2f154cafd6e3aafd4cae",
            log_index=148,
            registration_momentum_height=5373146,
            network_class=2,
            chain_id=1,
            to_address="z1qp53j4f49te2ydtepjg9wkpxjp62k3qy4mgdwg",
            token_address="0xb2e96a63479c2edd2fd62b382c89d5ca79f572d3",
            token_standard="zts1znnxxxxxxxxxxxxx9z4ulx",
            token_symbol="ZNN",
            token_decimals=8,
            amount=Decimal("50000000"),
            signature="test_signature_3",
            redeemed=False,
            revoked=False,
            redeemable_in=10,
        ),
    ]
    for req in requests:
        test_session.add(req)
    await test_session.commit()
    return requests


class TestBridgeSyncStatus:
    """Tests for bridge sync status endpoint."""

    @pytest.mark.asyncio
    async def test_get_sync_status_incomplete(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
    ):
        """Test sync status when sync is not complete."""
        token, _ = test_api_token

        # Ensure sync flag is not set
        await test_redis.delete(BRIDGE_SYNC_COMPLETE_KEY)

        response = await client.get(
            "/api/v1/bridge/sync-status",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sync_complete"] is False
        assert data["wrap_count"] == 0
        assert data["unwrap_count"] == 0

    @pytest.mark.asyncio
    async def test_get_sync_status_complete(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
        sample_wrap_requests,
        sample_unwrap_requests,
    ):
        """Test sync status when sync is complete."""
        token, _ = test_api_token

        # Set sync complete flag
        await test_redis.set(BRIDGE_SYNC_COMPLETE_KEY, "1")

        response = await client.get(
            "/api/v1/bridge/sync-status",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sync_complete"] is True
        assert data["wrap_count"] == 2
        assert data["unwrap_count"] == 3


class TestBridgeWraps:
    """Tests for wrap token request endpoints."""

    @pytest.mark.asyncio
    async def test_get_wraps_sync_not_complete(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
    ):
        """Test wraps endpoint returns 503 when sync not complete."""
        token, _ = test_api_token

        # Ensure sync flag is not set
        await test_redis.delete(BRIDGE_SYNC_COMPLETE_KEY)

        response = await client.get(
            "/api/v1/bridge/wraps",
            headers=auth_headers(token),
        )

        assert response.status_code == 503
        assert "Retry-After" in response.headers

    @pytest.mark.asyncio
    async def test_get_wraps(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
        sample_wrap_requests,
    ):
        """Test getting wrap requests."""
        token, _ = test_api_token
        await test_redis.set(BRIDGE_SYNC_COMPLETE_KEY, "1")

        response = await client.get(
            "/api/v1/bridge/wraps",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["page"] == 0
        assert data["page_size"] == 50
        assert len(data["items"]) == 2
        # Should be sorted by momentum height DESC
        assert data["items"][0]["creation_momentum_height"] == 11919422
        assert data["items"][1]["creation_momentum_height"] == 11919421

    @pytest.mark.asyncio
    async def test_get_wraps_with_pagination(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
        sample_wrap_requests,
    ):
        """Test wrap requests pagination."""
        token, _ = test_api_token
        await test_redis.set(BRIDGE_SYNC_COMPLETE_KEY, "1")

        response = await client.get(
            "/api/v1/bridge/wraps?page=0&page_size=1",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["page_size"] == 1
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_wraps_filter_by_token_symbol(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
        sample_wrap_requests,
    ):
        """Test filtering wrap requests by token symbol."""
        token, _ = test_api_token
        await test_redis.set(BRIDGE_SYNC_COMPLETE_KEY, "1")

        response = await client.get(
            "/api/v1/bridge/wraps?token_symbol=QSR",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["items"][0]["token_symbol"] == "QSR"

    @pytest.mark.asyncio
    async def test_get_wraps_filter_by_confirmations(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
        sample_wrap_requests,
    ):
        """Test filtering wrap requests by confirmations_to_finality."""
        token, _ = test_api_token
        await test_redis.set(BRIDGE_SYNC_COMPLETE_KEY, "1")

        # Both sample requests have confirmations_to_finality=0
        response = await client.get(
            "/api/v1/bridge/wraps?confirmations_to_finality=0",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        for item in data["items"]:
            assert item["confirmations_to_finality"] == 0

        # No requests with confirmations_to_finality=5
        response = await client.get(
            "/api/v1/bridge/wraps?confirmations_to_finality=5",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_get_wraps_unauthorized(self, client: AsyncClient):
        """Test wraps endpoint without auth."""
        response = await client.get("/api/v1/bridge/wraps")
        assert response.status_code == 401


class TestBridgeUnwraps:
    """Tests for unwrap token request endpoints."""

    @pytest.mark.asyncio
    async def test_get_unwraps_sync_not_complete(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
    ):
        """Test unwraps endpoint returns 503 when sync not complete."""
        token, _ = test_api_token

        # Ensure sync flag is not set
        await test_redis.delete(BRIDGE_SYNC_COMPLETE_KEY)

        response = await client.get(
            "/api/v1/bridge/unwraps",
            headers=auth_headers(token),
        )

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_get_unwraps(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
        sample_unwrap_requests,
    ):
        """Test getting unwrap requests."""
        token, _ = test_api_token
        await test_redis.set(BRIDGE_SYNC_COMPLETE_KEY, "1")

        response = await client.get(
            "/api/v1/bridge/unwraps",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert len(data["items"]) == 3
        # Should be sorted by momentum height DESC
        assert data["items"][0]["registration_momentum_height"] == 5373146

    @pytest.mark.asyncio
    async def test_get_unwraps_filter_by_redeemed(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
        sample_unwrap_requests,
    ):
        """Test filtering unwrap requests by redeemed status."""
        token, _ = test_api_token
        await test_redis.set(BRIDGE_SYNC_COMPLETE_KEY, "1")

        # Get only redeemed
        response = await client.get(
            "/api/v1/bridge/unwraps?redeemed=true",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        for item in data["items"]:
            assert item["redeemed"] is True

        # Get only not redeemed
        response = await client.get(
            "/api/v1/bridge/unwraps?redeemed=false",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["items"][0]["redeemed"] is False

    @pytest.mark.asyncio
    async def test_get_unwraps_filter_by_to_address(
        self,
        client: AsyncClient,
        test_api_token,
        test_redis,
        sample_unwrap_requests,
    ):
        """Test filtering unwrap requests by destination address."""
        token, _ = test_api_token
        await test_redis.set(BRIDGE_SYNC_COMPLETE_KEY, "1")

        response = await client.get(
            "/api/v1/bridge/unwraps?to_address=z1qr9vtwsfr2n0nsxl2nfh6l5esqjh2wfj85cfq9",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["items"][0]["to_address"] == "z1qr9vtwsfr2n0nsxl2nfh6l5esqjh2wfj85cfq9"

    @pytest.mark.asyncio
    async def test_get_unwraps_unauthorized(self, client: AsyncClient):
        """Test unwraps endpoint without auth."""
        response = await client.get("/api/v1/bridge/unwraps")
        assert response.status_code == 401
