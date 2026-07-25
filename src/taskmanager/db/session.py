from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from taskmanager.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """One session per unit of work, not per request (see README) — committed
    on success, rolled back on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
