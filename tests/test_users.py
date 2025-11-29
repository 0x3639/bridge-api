"""
Tests for user management endpoints (admin only).
"""
import uuid

import pytest
from httpx import AsyncClient

from src.models.user import User
from tests.conftest import auth_headers


class TestUserList:
    """Tests for listing users."""

    @pytest.mark.asyncio
    async def test_list_users_admin(
        self,
        client: AsyncClient,
        admin_api_token,
        test_user: User,
    ):
        """Test listing users as admin."""
        token, _ = admin_api_token

        response = await client.get(
            "/api/v1/users",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_users_non_admin(
        self,
        client: AsyncClient,
        test_api_token,
    ):
        """Test listing users as non-admin (should fail)."""
        token, _ = test_api_token

        response = await client.get(
            "/api/v1/users",
            headers=auth_headers(token),
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_users_unauthorized(self, client: AsyncClient):
        """Test listing users without auth."""
        response = await client.get("/api/v1/users")

        assert response.status_code == 401


class TestUserCreate:
    """Tests for creating users."""

    @pytest.mark.asyncio
    async def test_create_user_admin(
        self,
        client: AsyncClient,
        admin_api_token,
    ):
        """Test creating a user as admin."""
        token, _ = admin_api_token
        unique_id = uuid.uuid4().hex[:8]

        response = await client.post(
            "/api/v1/users",
            json={
                "username": f"newuser_{unique_id}",
                "email": f"newuser_{unique_id}@example.com",
                "password": "newpassword123",
            },
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == f"newuser_{unique_id}"
        assert data["email"] == f"newuser_{unique_id}@example.com"
        assert data["is_active"] is True
        assert data["is_admin"] is False
        # Password should not be returned
        assert "password" not in data
        assert "password_hash" not in data

    @pytest.mark.asyncio
    async def test_create_admin_user(
        self,
        client: AsyncClient,
        admin_api_token,
    ):
        """Test creating an admin user."""
        token, _ = admin_api_token
        unique_id = uuid.uuid4().hex[:8]

        response = await client.post(
            "/api/v1/users",
            json={
                "username": f"newadmin_{unique_id}",
                "email": f"newadmin_{unique_id}@example.com",
                "password": "adminpassword123",
                "is_admin": True,
            },
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_admin"] is True

    @pytest.mark.asyncio
    async def test_create_user_non_admin(
        self,
        client: AsyncClient,
        test_api_token,
    ):
        """Test creating user as non-admin (should fail)."""
        token, _ = test_api_token

        response = await client.post(
            "/api/v1/users",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "newpassword123",
            },
            headers=auth_headers(token),
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(
        self,
        client: AsyncClient,
        admin_api_token,
        test_user: User,
    ):
        """Test creating user with duplicate username."""
        token, _ = admin_api_token

        response = await client.post(
            "/api/v1/users",
            json={
                "username": test_user.username,  # Already exists
                "email": "different@example.com",
                "password": "newpassword123",
            },
            headers=auth_headers(token),
        )

        assert response.status_code in [400, 409, 422]


class TestUserDetail:
    """Tests for getting user details."""

    @pytest.mark.asyncio
    async def test_get_user_admin(
        self,
        client: AsyncClient,
        admin_api_token,
        test_user: User,
    ):
        """Test getting user details as admin."""
        token, _ = admin_api_token

        response = await client.get(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_get_user_not_found(
        self,
        client: AsyncClient,
        admin_api_token,
    ):
        """Test getting non-existent user."""
        token, _ = admin_api_token

        response = await client.get(
            "/api/v1/users/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(token),
        )

        assert response.status_code == 404


class TestUserUpdate:
    """Tests for updating users."""

    @pytest.mark.asyncio
    async def test_update_user_admin(
        self,
        client: AsyncClient,
        admin_api_token,
        test_user: User,
    ):
        """Test updating user as admin."""
        token, _ = admin_api_token

        response = await client.patch(
            f"/api/v1/users/{test_user.id}",
            json={"email": "updated@example.com"},
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "updated@example.com"

    @pytest.mark.asyncio
    async def test_update_user_rate_limits(
        self,
        client: AsyncClient,
        admin_api_token,
        test_user: User,
    ):
        """Test updating user rate limits."""
        token, _ = admin_api_token

        response = await client.patch(
            f"/api/v1/users/{test_user.id}",
            json={
                "rate_limit_per_second": 50,
                "rate_limit_burst": 100,
            },
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rate_limit_per_second"] == 50
        assert data["rate_limit_burst"] == 100


class TestUserDelete:
    """Tests for deleting (deactivating) users."""

    @pytest.mark.asyncio
    async def test_delete_user_admin(
        self,
        client: AsyncClient,
        admin_api_token,
        test_user: User,
    ):
        """Test deactivating user as admin."""
        token, _ = admin_api_token

        response = await client.delete(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_user_non_admin(
        self,
        client: AsyncClient,
        test_api_token,
        admin_user: User,
    ):
        """Test deleting user as non-admin (should fail)."""
        token, _ = test_api_token

        response = await client.delete(
            f"/api/v1/users/{admin_user.id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 403
