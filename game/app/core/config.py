"""Application configuration."""
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    # Database
    db_host: str = "localhost"
    db_port: int = 5433
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "game_service"

    # Application
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8001
    app_name: str = "game_service"

    # Bot-facing API
    # Backward-compat flag: when True, snapshot includes legacy fields
    # (e.g. dealer_cards/current_position/can_start/start_error).
    bot_snapshot_include_legacy_fields: bool = True

    @property
    def database_url(self) -> str:
        """Get database connection URL."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
