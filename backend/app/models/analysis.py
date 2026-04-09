from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.database import Base


class ProjectAnalysis(Base):
    __tablename__ = "project_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coingecko_id: Mapped[str] = mapped_column(String, index=True)

    # Stage 2 scores
    tokenomics_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    github_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    onchain_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    audit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    holder_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Stage 3 scores
    smart_money_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    narrative_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    penalty_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Stage 4 scores
    social_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    exchange_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full analysis data per module
    tokenomics_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    github_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    onchain_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audit_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    holder_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    whale_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    narrative_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    red_flag_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    social_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    exchange_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    red_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)

    analysed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
