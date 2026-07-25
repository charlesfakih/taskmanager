import os
from pathlib import Path

from dotenv import load_dotenv

# Point the app at the test database *before* any `taskmanager.*` module is
# imported -- Settings() is a module-level singleton built at import time,
# so this has to happen first, at the top of conftest.py.
load_dotenv()
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://taskmanager@localhost:5433/taskmanager_test"
)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from taskmanager.db.session import engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db():
    """Run the real Alembic migrations against the test DB once per session
    (not `Base.metadata.create_all()`) so the test suite also exercises the
    actual migration path, not a shortcut around it."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
async def _clean_db():
    """Table truncation between tests, not per-test transaction rollback.

    The app opens a fresh AsyncSession per unit of work (see db/session.py)
    rather than accepting an injected/shared session, so the standard
    "wrap each test in an outer transaction + savepoint" isolation recipe
    would require monkeypatching the session factory. Truncating is simpler,
    doesn't fight the app's architecture, and -- unlike the savepoint
    approach -- doesn't complicate the true-concurrency tests, which need
    real, independently-committing connections anyway.
    """
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE tasks, projects, users RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
async def client():
    from taskmanager.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
