from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, JSON, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coingecko_id: Mapped[str] = mapped_column(String, index=True)
    project_name: Mapped[str] = mapped_column(String)
    alert_type: Mapped[str] = mapped_column(String)  # score_high, whale, red_flag, listing
    severity: Mapped[str] = mapped_column(String, default="info")  # info, warning, critical
    title: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sent_telegram: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_email: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
