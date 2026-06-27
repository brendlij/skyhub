from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NodeDeviceSettings(Base):
    __tablename__ = "node_device_settings"

    node_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    devices: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
