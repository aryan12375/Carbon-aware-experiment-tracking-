"""
app/db/session.py
=================
Async SQLAlchemy engine + session factory.
Uses aiosqlite for SQLite in dev and asyncpg for Postgres in production.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────
# connect_args only needed for SQLite (disables same-thread check for async)
_connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,           # logs all SQL in development
    future=True,
    connect_args=_connect_args,
)

# ── Session factory ───────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,        # avoids lazy-load issues after commit
    autocommit=False,
    autoflush=False,
)


# ── Base model ────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async database session.
    Automatically rolls back on exception and closes on exit.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (used at startup in development)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
