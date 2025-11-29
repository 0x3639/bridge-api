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

    # Security
    secret_key: str = "change-this-to-a-secure-random-string"
    api_token_prefix: str = "ora_"
    access_token_expire_minutes: int = 15

    # Database
    database_url: str = "postgresql+asyncpg://orchapi:password@localhost:5432/orchestrator"

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
