from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coingecko_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    ticker: Mapped[str] = mapped_column(String)
    chain: Mapped[str | None] = mapped_column(String, nullable=True)

    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
