"""Poller service configuration."""
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_base_url: str = Field(
        default="https://api.telegram.org", alias="TELEGRAM_BASE_URL"
    )
    telegram_poll_timeout: int = Field(default=30, alias="TELEGRAM_POLL_TIMEOUT")
    telegram_poll_limit: int = Field(default=100, alias="TELEGRAM_POLL_LIMIT")
    telegram_request_timeout: int = Field(
        default=35,
        alias="TELEGRAM_REQUEST_TIMEOUT",
    )
    telegram_retry_base_delay: float = Field(
        default=1.0,
        alias="TELEGRAM_RETRY_BASE_DELAY",
    )
    telegram_retry_max_delay: float = Field(
        default=30.0,
        alias="TELEGRAM_RETRY_MAX_DELAY",
    )

    offset_state_path: str = Field(
        default="./var/state/offset.json", alias="OFFSET_STATE_PATH"
    )

    kafka_bootstrap_servers: str = Field(
        default="localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS"
    )
    kafka_topic_updates: str = Field(
        default="telegram.updates.raw", alias="KAFKA_TOPIC_UPDATES"
    )
    kafka_client_id: str = Field(default="telegram_poller", alias="KAFKA_CLIENT_ID")
    kafka_required_acks: str = Field(default="all", alias="KAFKA_REQUIRED_ACKS")

    worker_count: int = Field(default=4, alias="WORKER_COUNT")
    max_in_flight_updates: int = Field(default=1000, alias="MAX_IN_FLIGHT_UPDATES")
    shutdown_timeout: int = Field(default=15, alias="SHUTDOWN_TIMEOUT")

    debug: bool = Field(default=True, alias="DEBUG")
    app_name: str = Field(default="telegram_poller", alias="APP_NAME")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
