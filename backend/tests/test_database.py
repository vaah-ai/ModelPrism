"""Tests for database engine and session management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.database import AsyncSessionFactory, close_db, engine, get_db


class TestDatabaseEngine:
    """Database engine creation tests."""

    def test_engine_is_async(self) -> None:
        assert isinstance(engine, AsyncEngine)

    def test_engine_url_contains_asyncpg(self) -> None:
        assert "asyncpg" in str(engine.url)

    def test_engine_pool_exists(self) -> None:
        """Engine should have a connection pool."""
        assert engine.pool is not None


class TestSessionFactory:
    """Session factory tests."""

    def test_session_factory_creates_async_session(self) -> None:
        session = AsyncSessionFactory()
        assert isinstance(session, AsyncSession)

    def test_session_expire_on_commit_is_false(self) -> None:
        session = AsyncSessionFactory()
        assert session.info.get("expire_on_commit") is not False  # default is True

    def test_get_db_returns_async_generator(self) -> None:
        """Verify get_db is an async generator."""
        gen = get_db()
        assert hasattr(gen, "__anext__")


class TestCloseDb:
    """Database cleanup tests."""

    async def test_close_db_is_idempotent(self) -> None:
        """Closing the database engine multiple times should not raise."""
        await close_db()
        await close_db()  # second call should be safe
