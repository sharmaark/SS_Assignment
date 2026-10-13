from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "notification"
    notification_port: int = 8004
    notification_mongodb_url: str = (
        "mongodb://notification_user:notification_pass@localhost:27017/"
        "notification_db?authSource=notification_db"
    )
    notification_mongodb_database: str = "notification_db"
    mock_mode: Literal["normal", "fail", "slow", "commit_then_slow"] = "normal"
    mock_delay_seconds: float = 2.0
    allow_mock_control: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
