from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NodeCameraSettings(Base):
    __tablename__ = "node_camera_settings"

    node_id: Mapped[str] = mapped_column(String(100), primary_key=True)

    interval_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=1920, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=1080, nullable=False)
    format: Mapped[str] = mapped_column(String(20), default="jpg", nullable=False)

    day_auto_exposure: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    day_exposure_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day_auto_gain: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    day_gain: Mapped[float | None] = mapped_column(Float, nullable=True)

    night_auto_exposure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    night_exposure_ms: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    night_auto_gain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    night_gain: Mapped[float] = mapped_column(Float, default=8, nullable=False)

    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
