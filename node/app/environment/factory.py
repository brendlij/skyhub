from app.config import NodeSettings
from app.environment.base import EnvironmentSensor
from app.environment.bme280_sensor import BME280Sensor
from app.environment.mock_sensor import MockEnvironmentSensor


def create_environment_sensor(settings: NodeSettings) -> EnvironmentSensor | None:
    driver = settings.environment_sensor_driver.lower()

    if driver in {"none", "disabled", "off"}:
        return None

    if driver == "mock":
        return MockEnvironmentSensor()

    if driver == "bme280":
        return BME280Sensor(
            bus=settings.bme280_i2c_bus,
            address=settings.bme280_i2c_address_int,
        )

    raise ValueError(f"Unknown environment sensor driver: {settings.environment_sensor_driver}")
