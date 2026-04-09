from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.watchlist import WatchlistItem, ScoreHistory
from app.core.logger import get_logger

logger = get_logger(__name__)


async def add_to_watchlist(
    session: AsyncSession,
    coingecko_id: str,
    project_name: str,
    ticker: str = "",
    notes: str | None = None,
) -> WatchlistItem:
    """Add a project to the watchlist."""
    existing = await session.execute(
        select(WatchlistItem).where(
            WatchlistItem.coingecko_id == coingecko_id
        )
    )
    item = existing.scalar_one_or_none()

    if item:
        item.notes = notes or item.notes
        logger.info(f"Updated watchlist item: {coingecko_id}")
    else:
        item = WatchlistItem(
            coingecko_id=coingecko_id,
            project_name=project_name,
            ticker=ticker,
            notes=notes,
        )
        session.add(item)
        logger.info(f"Added to watchlist: {coingecko_id}")

    await session.commit()
    return item


async def remove_from_watchlist(
    session: AsyncSession,
    coingecko_id: str,
) -> bool:
    """Remove a project from the watchlist."""
    result = await session.execute(
        delete(WatchlistItem).where(
            WatchlistItem.coingecko_id == coingecko_id
        )
    )
    await session.commit()
    removed = result.rowcount > 0
    if removed:
        logger.info(f"Removed from watchlist: {coingecko_id}")
    return removed


async def get_watchlist(session: AsyncSession) -> list[dict]:
    """Get all watchlist items with latest score."""
    result = await session.execute(
        select(WatchlistItem).order_by(WatchlistItem.added_at.desc())
    )
    items = result.scalars().all()

    watchlist = []
    for item in items:
        # Get latest score
        score_result = await session.execute(
            select(ScoreHistory)
            .where(ScoreHistory.coingecko_id == item.coingecko_id)
            .order_by(ScoreHistory.recorded_at.desc())
            .limit(1)
        )
        latest_score = score_result.scalar_one_or_none()

        # Get score history (last 10)
        history_result = await session.execute(
            select(ScoreHistory)
            .where(ScoreHistory.coingecko_id == item.coingecko_id)
            .order_by(ScoreHistory.recorded_at.desc())
            .limit(10)
        )
        history = history_result.scalars().all()

        watchlist.append({
            "coingecko_id": item.coingecko_id,
            "project_name": item.project_name,
            "ticker": item.ticker,
            "notes": item.notes,
            "added_at": item.added_at.isoformat()
            if item.added_at else None,
            "latest_score": latest_score.total_score
            if latest_score else None,
            "score_history": [
                {
                    "score": h.total_score,
                    "categories": h.categories,
                    "recorded_at": h.recorded_at.isoformat()
                    if h.recorded_at else None,
                }
                for h in reversed(history)
            ],
        })

    return watchlist


async def record_score(
    session: AsyncSession,
    coingecko_id: str,
    total_score: float,
    categories: dict | None = None,
) -> None:
    """Save a score snapshot for history tracking.
    Does NOT commit — caller is responsible for committing."""
    entry = ScoreHistory(
        coingecko_id=coingecko_id,
        total_score=total_score,
        categories=categories,
    )
    session.add(entry)
