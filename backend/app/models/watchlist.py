from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coingecko_id: Mapped[str] = mapped_column(
        String, unique=True, index=True
    )
    project_name: Mapped[str] = mapped_column(String)
    ticker: Mapped[str] = mapped_column(String, default="")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coingecko_id: Mapped[str] = mapped_column(String, index=True)
    total_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    categories: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
