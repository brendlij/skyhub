from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class EnvironmentReading:
    temperature_c: float
    humidity_percent: float
    pressure_hpa: float | None = None
    dew_point_c: float | None = None
    captured_at: datetime | None = None

    def to_message_payload(self) -> dict:
        captured_at = self.captured_at or datetime.now(timezone.utc)
        return {
            "temperature_c": round(self.temperature_c, 2),
            "humidity_percent": round(self.humidity_percent, 2),
            "pressure_hpa": round(self.pressure_hpa, 2) if self.pressure_hpa is not None else None,
            "dew_point_c": round(self.dew_point_c, 2) if self.dew_point_c is not None else None,
            "captured_at": captured_at.isoformat(),
        }


class EnvironmentSensor:
    driver: str = "base"

    def read(self) -> EnvironmentReading:
        raise NotImplementedError
