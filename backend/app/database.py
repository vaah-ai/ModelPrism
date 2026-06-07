"""Async SQLAlchemy engine and session management.

Provides:
- ``engine`` — the async engine (singleton)
- ``AsyncSession`` — session factory
- ``get_db`` — FastAPI dependency yielding an AsyncSession per request
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    str(settings.database_url),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    echo=settings.database_echo,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession per request.

    The session is automatically committed on success, rolled back on
    exception, and closed when the request completes.
    """
    session = AsyncSessionFactory()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    finally:
        await session.close()


async def verify_db_connection() -> bool:
    """Verify the database is reachable by running a simple query.

    Returns True if connected, False otherwise.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        logger.warning("Database connection check failed: %s", exc)
        return False


async def close_db() -> None:
    """Dispose of the database engine and release all connections."""
    await engine.dispose()
    logger.info("Database engine disposed")
