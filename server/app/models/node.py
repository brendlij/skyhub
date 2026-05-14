from datetime import datetime

from sqlalchemy import DateTime, String, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Node(Base):
    __tablename__ = "nodes"

    node_id: Mapped[str] = mapped_column(String(100), primary_key=True)

    online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_type: Mapped[str | None] = mapped_column(String(100), nullable=True)