import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.storage.database import Base
from app.models.project import Project
from app.services.project_service import upsert_projects

engine = create_async_engine("sqlite+aiosqlite:///:memory:")
TestSession = async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    async with TestSession() as session:
        yield session


@pytest.mark.asyncio
async def test_upsert_inserts_new_projects(db: AsyncSession):
    projects = [
        {"id": "token-a", "name": "Token A", "ticker": "TA", "market_cap": 1000000, "volume_24h": 200000, "price": 0.5},
        {"id": "token-b", "name": "Token B", "ticker": "TB", "market_cap": 5000000, "volume_24h": 800000, "price": 1.2},
    ]
    saved = await upsert_projects(db, projects)
    assert saved == 2

    result = await db.execute(select(Project))
    all_projects = result.scalars().all()
    assert len(all_projects) == 2


@pytest.mark.asyncio
async def test_upsert_updates_existing_project(db: AsyncSession):
    projects = [{"id": "token-a", "name": "Token A", "ticker": "TA", "market_cap": 1000000}]
    await upsert_projects(db, projects)

    updated = [{"id": "token-a", "name": "Token A", "ticker": "TA", "market_cap": 2000000}]
    await upsert_projects(db, updated)

    result = await db.execute(select(Project).where(Project.coingecko_id == "token-a"))
    p = result.scalar_one()
    assert p.market_cap == 2000000


@pytest.mark.asyncio
async def test_upsert_skips_projects_without_id(db: AsyncSession):
    projects = [{"name": "No ID", "ticker": "NI"}]
    saved = await upsert_projects(db, projects)
    assert saved == 0
