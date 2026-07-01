from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.capture_storage_settings import CaptureStorageSettings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CaptureStorageSettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self) -> CaptureStorageSettings:
        settings = self.db.get(CaptureStorageSettings, "default")

        if settings is None:
            settings = CaptureStorageSettings(
                settings_id="default",
                day_capture_enabled=True,
                night_capture_enabled=True,
                retention_days=None,
                max_storage_gb=None,
                updated_at=utc_now(),
            )
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)

        return settings

    def update(self, values: dict[str, Any]) -> CaptureStorageSettings:
        settings = self.get_or_create()

        for field_name, value in values.items():
            setattr(settings, field_name, value)

        settings.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(settings)

        return settings
