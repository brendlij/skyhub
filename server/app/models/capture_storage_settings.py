from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CaptureStorageSettings(Base):
    __tablename__ = "capture_storage_settings"

    settings_id: Mapped[str] = mapped_column(String(50), primary_key=True, default="default")
    day_capture_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    night_capture_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_storage_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
