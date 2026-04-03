from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.database import Base


class ProjectAnalysis(Base):
    __tablename__ = "project_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coingecko_id: Mapped[str] = mapped_column(String, index=True)

    # Scores per module
    tokenomics_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    github_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    onchain_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    audit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    holder_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full analysis data per module
    tokenomics_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    github_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    onchain_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audit_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    holder_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    red_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    analysed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
