from app.config import NodeSettings
from app.heater.base import HeaterController
from app.heater.gpiozero_heater import GpiozeroHeaterController
from app.heater.mock_heater import MockHeaterController


def create_heater_controller(settings: NodeSettings) -> HeaterController | None:
    driver = settings.heater_driver.lower()

    if driver in {"none", "disabled", "off"}:
        return None

    if driver == "mock":
        return MockHeaterController(gpio_pin=settings.heater_gpio_pin)

    if driver == "gpiozero":
        return GpiozeroHeaterController(
            gpio_pin=settings.heater_gpio_pin,
            active_high=settings.heater_active_high,
        )

    raise ValueError(f"Unknown heater driver: {settings.heater_driver}")
