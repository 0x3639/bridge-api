"""
Pytest configuration and fixtures for testing the Bridge API.

Uses testcontainers to spin up PostgreSQL and Redis containers for testing.
Each test gets a fresh database state.
"""
import asyncio
import uuid
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from src.core.security import generate_api_token, hash_password
from src.models.base import Base
from src.models.orchestrator import OrchestratorNode
from src.models.token import ApiToken
from src.models.user import User


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for the test session."""
    container = PostgresContainer(
        image="postgres:16-alpine",
        username="testuser",
        password="testpass",
        dbname="testdb",
    )
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def redis_container():
    """Start a Redis container for the test session."""
    container = RedisContainer(image="redis:7-alpine")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def database_url(postgres_container) -> str:
    """Get the async database URL for the test PostgreSQL container."""
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://testuser:testpass@{host}:{port}/testdb"


@pytest.fixture(scope="session")
def redis_url(redis_container) -> str:
    """Get the Redis URL for the test Redis container."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


@pytest_asyncio.fixture(scope="function")
async def test_engine(database_url) -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine for each test function."""
    engine = create_async_engine(database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def test_redis(redis_url) -> AsyncGenerator[Redis, None]:
    """Create a real Redis client connected to test container."""
    redis = Redis.from_url(redis_url, decode_responses=True)
    yield redis
    await redis.flushdb()
    await redis.aclose()


@pytest_asyncio.fixture(scope="function")
async def client(test_session, test_redis) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with overridden dependencies."""
    # Import here to avoid circular imports and ensure fresh app state
    from src.dependencies import get_db, get_redis
    from src.main import app

    async def override_get_db():
        yield test_session

    async def override_get_redis():
        return test_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(test_session) -> User:
    """Create a test user."""
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        username=f"testuser_{unique_id}",
        email=f"test_{unique_id}@example.com",
        password_hash=hash_password("testpassword"),
        is_active=True,
        is_admin=False,
        rate_limit_per_second=10,
        rate_limit_burst=20,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def admin_user(test_session) -> User:
    """Create an admin test user."""
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        username=f"adminuser_{unique_id}",
        email=f"admin_{unique_id}@example.com",
        password_hash=hash_password("adminpassword"),
        is_active=True,
        is_admin=True,
        rate_limit_per_second=100,
        rate_limit_burst=200,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_api_token(test_session, test_user) -> tuple[str, ApiToken]:
    """Create a test API token, returns (raw_token, token_record)."""
    token, token_hash = generate_api_token()

    api_token = ApiToken(
        user_id=test_user.id,
        token_hash=token_hash,
        name="Test Token",
        expires_at=None,
    )
    test_session.add(api_token)
    await test_session.commit()
    await test_session.refresh(api_token)

    return token, api_token


@pytest_asyncio.fixture(scope="function")
async def admin_api_token(test_session, admin_user) -> tuple[str, ApiToken]:
    """Create an admin API token, returns (raw_token, token_record)."""
    token, token_hash = generate_api_token()

    api_token = ApiToken(
        user_id=admin_user.id,
        token_hash=token_hash,
        name="Admin Token",
        expires_at=None,
    )
    test_session.add(api_token)
    await test_session.commit()
    await test_session.refresh(api_token)

    return token, api_token


@pytest_asyncio.fixture(scope="function")
async def test_orchestrator_node(test_session) -> OrchestratorNode:
    """Create a test orchestrator node."""
    unique_id = uuid.uuid4().hex[:8]
    node = OrchestratorNode(
        name=f"TestNode_{unique_id}",
        ip_address="192.168.1.1",
        pubkey=f"test_pubkey_{unique_id}",
        is_active=True,
    )
    test_session.add(node)
    await test_session.commit()
    await test_session.refresh(node)
    return node


def auth_headers(token: str) -> dict:
    """Create authorization headers for a token."""
    return {"Authorization": f"Bearer {token}"}
