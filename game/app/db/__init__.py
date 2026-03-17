"""Database initialization and session management."""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


class DatabaseManager:
    """Database connection and session management."""

    def __init__(self):
        self.engine = None
        self.async_session = None

    async def init(self) -> None:
        """Initialize database engine and session factory."""
        self.engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            future=True,
        )
        
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        # Schema bootstrap is intentionally disabled.
        # The database schema must be managed via Alembic migrations.

    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()


db = DatabaseManager()


async def get_db() -> AsyncIterator[AsyncSession]:
    """Dependency for getting database session."""
    async with db.async_session() as session:
        yield session
