from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project
from app.core.logger import get_logger

logger = get_logger(__name__)

CACHE_TTL = timedelta(hours=6)


async def upsert_projects(session: AsyncSession, projects: list[dict]) -> int:
    """Insert or update projects from scan results. Returns count of saved projects."""
    saved = 0
    for p in projects:
        coingecko_id = p.get("id")
        if not coingecko_id:
            continue

        stmt = select(Project).where(Project.coingecko_id == coingecko_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = p.get("name", existing.name)
            existing.ticker = p.get("ticker", existing.ticker)
            existing.market_cap = p.get("market_cap")
            existing.volume_24h = p.get("volume_24h")
            existing.price = p.get("price")
            existing.age_days = p.get("age_days")
            existing.raw_data = p
        else:
            existing = Project(
                coingecko_id=coingecko_id,
                name=p.get("name", ""),
                ticker=p.get("ticker", ""),
                market_cap=p.get("market_cap"),
                volume_24h=p.get("volume_24h"),
                price=p.get("price"),
                age_days=p.get("age_days"),
                raw_data=p,
            )
            session.add(existing)
        saved += 1

    await session.commit()
    logger.info(f"Saved {saved} projects to DB")
    return saved


async def is_cache_fresh(session: AsyncSession) -> bool:
    """Check if we have recent scan data (< 6 hours old)."""
    result = await session.execute(select(func.max(Project.updated_at)))
    last_update = result.scalar_one_or_none()
    if last_update is None:
        return False
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - last_update
    logger.info(f"Cache age: {age}, TTL: {CACHE_TTL}, fresh: {age < CACHE_TTL}")
    return age < CACHE_TTL


async def get_cached_projects(session: AsyncSession) -> list[dict]:
    """Return projects from DB as dicts (same format as scan results)."""
    result = await session.execute(select(Project).order_by(Project.market_cap.asc()))
    projects = result.scalars().all()
    return [
        {
            "id": p.coingecko_id,
            "name": p.name,
            "ticker": p.ticker,
            "price": p.price,
            "market_cap": p.market_cap,
            "volume_24h": p.volume_24h,
            "volume_to_mcap_ratio": round(p.volume_24h / p.market_cap, 4)
            if p.market_cap and p.volume_24h
            else None,
            "age_days": p.age_days,
            "image": (p.raw_data or {}).get("image"),
            "price_change_24h": (p.raw_data or {}).get("price_change_24h"),
            "source": "cache",
        }
        for p in projects
    ]
