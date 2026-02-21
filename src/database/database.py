from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from loguru import logger

from src.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Dependency that provides a database session."""
    async with async_session() as session:
        yield session


async def init_db() -> None:
    """Create all tables if they don't exist."""
    from src.database.models import Base  # noqa: F811

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")


async def close_db() -> None:
    """Dispose the engine connection pool."""
    await engine.dispose()
    logger.info("Database connection closed")
