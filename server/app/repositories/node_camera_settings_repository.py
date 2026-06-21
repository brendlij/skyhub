from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.node_camera_settings import NodeCameraSettings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NodeCameraSettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, node_id: str) -> NodeCameraSettings | None:
        return self.db.get(NodeCameraSettings, node_id)

    def get_or_create(self, node_id: str) -> NodeCameraSettings:
        settings = self.get(node_id)

        if settings is None:
            settings = NodeCameraSettings(node_id=node_id, updated_at=utc_now())
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)

        return settings

    def update(self, node_id: str, values: dict[str, Any]) -> NodeCameraSettings:
        settings = self.get_or_create(node_id)

        for field_name, value in values.items():
            if field_name == "format" and value == "":
                value = "jpg"

            if value is not None:
                setattr(settings, field_name, value)

        settings.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(settings)

        return settings

    def delete(self, node_id: str) -> bool:
        settings = self.get(node_id)

        if settings is None:
            return False

        self.db.delete(settings)
        self.db.commit()

        return True
