from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="router", alias="APP_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    game_service_base_url: str = Field(
        default="http://localhost:8001",
        alias="GAME_SERVICE_BASE_URL",
    )
    game_service_request_timeout_seconds: float = Field(
        default=10.0,
        alias="GAME_SERVICE_REQUEST_TIMEOUT_SECONDS",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )
    dedup_ttl_seconds: int = Field(
        default=86400,
        alias="DEDUP_TTL_SECONDS",
    )
    timer_retention_seconds: int = Field(
        default=7200,
        alias="TIMER_RETENTION_SECONDS",
    )
    session_context_ttl_seconds: int = Field(
        default=7200,
        alias="SESSION_CONTEXT_TTL_SECONDS",
    )
    timer_poll_interval_seconds: float = Field(
        default=0.5,
        alias="TIMER_POLL_INTERVAL_SECONDS",
    )
    timer_claim_ttl_seconds: int = Field(
        default=30,
        alias="TIMER_CLAIM_TTL_SECONDS",
    )
    sender_request_timeout_seconds: float = Field(
        default=10.0,
        alias="SENDER_REQUEST_TIMEOUT_SECONDS",
    )
    telegram_base_url: str = Field(
        default="https://api.telegram.org",
        alias="TELEGRAM_BASE_URL",
    )
    telegram_bot_token: str = Field(
        default="",
        alias="TELEGRAM_BOT_TOKEN",
    )
    kafka_client_id: str = Field(
        default="router-consumer",
        alias="KAFKA_CLIENT_ID",
    )
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        alias="KAFKA_BOOTSTRAP_SERVERS",
    )
    kafka_topic_updates: str = Field(
        default="telegram.updates.raw",
        alias="KAFKA_TOPIC_UPDATES",
    )
    kafka_group_id: str = Field(
        default="router-verifier",
        alias="KAFKA_GROUP_ID",
    )
    kafka_auto_offset_reset: str = Field(
        default="latest",
        alias="KAFKA_AUTO_OFFSET_RESET",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def get_settings() -> Settings:
    return Settings()