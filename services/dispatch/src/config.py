from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "dispatch"
    dispatch_port: int = 8003
    dispatch_database_url: str = "postgresql+psycopg://dispatch_user:dispatch_pass@localhost:55432/dispatch_db"
    work_order_url: str = "http://localhost:8001"
    workforce_url: str = "http://localhost:8002"
    notification_url: str = "http://localhost:8004"
    downstream_timeout_seconds: float = 1.0
    notification_max_attempts: int = 3
    retry_base_seconds: float = 0.15
    idempotency_wait_seconds: float = 8.0
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
