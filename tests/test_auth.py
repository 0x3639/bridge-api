"""
Tests for authentication endpoints.
"""
import pytest
from httpx import AsyncClient

from src.core.security import hash_password
from src.models.user import User
from tests.conftest import auth_headers


class TestLogin:
    """Tests for the login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login with valid credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": test_user.username, "password": "testpassword"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client: AsyncClient, test_user: User):
        """Test login with invalid password."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": test_user.username, "password": "wrongpassword"},
        )

        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_invalid_username(self, client: AsyncClient):
        """Test login with non-existent username."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "testpassword"},
        )

        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_inactive_user(
        self, client: AsyncClient, test_session, test_user: User
    ):
        """Test login with inactive user."""
        test_user.is_active = False
        await test_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"username": test_user.username, "password": "testpassword"},
        )

        assert response.status_code == 401
        assert "disabled" in response.json()["detail"].lower()


class TestTokenManagement:
    """Tests for API token management."""

    @pytest.mark.asyncio
    async def test_create_token(
        self, client: AsyncClient, test_user: User, test_api_token
    ):
        """Test creating a new API token."""
        token, _ = test_api_token

        response = await client.post(
            "/api/v1/auth/tokens",
            json={"name": "New Test Token"},
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["name"] == "New Test Token"
        assert data["token"].startswith("ora_")

    @pytest.mark.asyncio
    async def test_create_token_unauthorized(self, client: AsyncClient):
        """Test creating token without authentication."""
        response = await client.post(
            "/api/v1/auth/tokens",
            json={"name": "Test Token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_tokens(
        self, client: AsyncClient, test_user: User, test_api_token
    ):
        """Test listing user's tokens."""
        token, _ = test_api_token

        response = await client.get(
            "/api/v1/auth/tokens",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert "tokens" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_revoke_token(
        self, client: AsyncClient, test_user: User, test_api_token, test_session
    ):
        """Test revoking an API token."""
        token, api_token = test_api_token

        response = await client.delete(
            f"/api/v1/auth/tokens/{api_token.id}",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_token(
        self, client: AsyncClient, test_api_token
    ):
        """Test revoking a non-existent token."""
        token, _ = test_api_token

        response = await client.delete(
            "/api/v1/auth/tokens/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(token),
        )

        assert response.status_code == 404


class TestCurrentUser:
    """Tests for current user endpoint."""

    @pytest.mark.asyncio
    async def test_get_current_user(
        self, client: AsyncClient, test_user: User, test_api_token
    ):
        """Test getting current user info."""
        token, _ = test_api_token

        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email
        assert data["is_admin"] is False

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test getting current user without auth."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token."""
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers("invalid_token"),
        )

        assert response.status_code == 401
