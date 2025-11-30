from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Orchestrator API"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    api_port: int = 8001

    # API Documentation
    docs_enabled: bool = True  # Enable/disable Swagger UI and ReDoc

    # Security
    secret_key: str = "change-this-to-a-secure-random-string"
    api_token_prefix: str = "ora_"
    access_token_expire_minutes: int = 15

    # CORS Configuration
    # Comma-separated list of allowed origins, or "*" for all (default)
    cors_origins: str = "*"

    # Security Headers
    # Enable HSTS (HTTP Strict Transport Security) - set to True in production with HTTPS
    hsts_enabled: bool = False
    hsts_max_age: int = 31536000  # 1 year in seconds

    # Login Rate Limiting (IP-based for unauthenticated endpoints)
    login_rate_limit_per_minute: int = 10
    login_rate_limit_burst: int = 5

    # Database
    database_url: str = "postgresql+asyncpg://orchapi:password@localhost:5432/orchestrator"

    # Database Connection Pool
    db_pool_size: int = 5  # Number of permanent connections
    db_max_overflow: int = 10  # Max additional connections during load
    db_pool_recycle: int = 3600  # Recycle connections after 1 hour (seconds)
    db_pool_pre_ping: bool = True  # Check connection health before use

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Rate Limiting Defaults
    default_rate_limit_per_second: int = 10
    default_rate_limit_burst: int = 20
    admin_rate_limit_per_second: int = 100
    admin_rate_limit_burst: int = 200

    # Orchestrator Collection
    orchestrator_poll_interval: int = 60
    orchestrator_rpc_timeout: int = 10
    orchestrator_rpc_port: int = 55000
    min_online_for_bridge: int = 16

    # Cache TTLs (seconds)
    cache_status_ttl: int = 10
    cache_user_ttl: int = 300
    cache_stats_ttl: int = 60

    # Bridge RPC settings
    bridge_rpc_url: str = "https://my.hc1node.com:35997"
    bridge_poll_interval: int = 60  # Seconds between data collection
    bridge_rpc_timeout: int = 30  # Longer timeout for paginated requests
    bridge_batch_size: int = 100  # Records per RPC request during sync

    # Bridge Worker Database Pool (separate from main API pool)
    bridge_db_pool_size: int = 2
    bridge_db_max_overflow: int = 1


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
