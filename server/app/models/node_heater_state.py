from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NodeHeaterState(Base):
    __tablename__ = "node_heater_state"

    node_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    desired_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    actual_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    driver: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gpio_pin: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
