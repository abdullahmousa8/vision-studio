import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def get_secret(secret_name: str, default: str | None = None) -> str | None:
    """Read a secret from Docker Secrets, falling back to an environment variable."""
    secret_path = f"/run/secrets/{secret_name}"
    if os.path.exists(secret_path):
        with open(secret_path, encoding="utf-8") as f:
            return f.read().strip()
    return os.getenv(secret_name.upper(), default)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "gemini-vision-studio"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://app:app_password@localhost:5432/gemini_vision"
    sync_database_url: str = "postgresql://app:app_password@localhost:5432/gemini_vision"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = get_secret("minio_access_key", "minioadmin")
    minio_secret_key: str = get_secret("minio_secret_key", "minioadmin")
    minio_bucket: str = "artifacts"
    minio_secure: bool = False

    # Models
    ollama_base_url: str = "http://localhost:11434"
    openrouter_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str | None = get_secret("openrouter_key")
    grok_url: str = "https://api.x.ai/v1"
    grok_api_key: str | None = get_secret("grok_key")

    # Auth
    jwt_secret_key: str = get_secret("jwt_secret", "change-me-in-production-32-char-min")
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60

    # Security
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    rate_limit_per_minute: int = 10

    # Budget
    daily_budget_usd: float = 5.0
    alert_threshold: float = 0.8

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
