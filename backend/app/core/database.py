from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


async_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
)

sync_engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)

async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

SessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async session."""
    async with async_session() as session:
        yield session


def get_sync_db():
    """Dependency for sync contexts (e.g. Celery tasks)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
