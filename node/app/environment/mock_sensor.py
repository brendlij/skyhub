from datetime import datetime, timezone

from app.environment.base import EnvironmentReading, EnvironmentSensor
from app.environment.calculations import dew_point_celsius


class MockEnvironmentSensor(EnvironmentSensor):
    driver = "mock"

    def read(self) -> EnvironmentReading:
        temperature_c = 12.4
        humidity_percent = 78.0
        return EnvironmentReading(
            temperature_c=temperature_c,
            humidity_percent=humidity_percent,
            pressure_hpa=1008.3,
            dew_point_c=dew_point_celsius(temperature_c, humidity_percent),
            captured_at=datetime.now(timezone.utc),
        )
