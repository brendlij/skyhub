from app.heater.base import HeaterController, HeaterState


class MockHeaterController(HeaterController):
    driver = "mock"

    def __init__(self, gpio_pin: int | None = None):
        self.gpio_pin = gpio_pin
        self.enabled = False

    def set_enabled(self, enabled: bool) -> HeaterState:
        self.enabled = bool(enabled)
        return self.get_state()

    def get_state(self) -> HeaterState:
        return HeaterState(
            enabled=self.enabled,
            driver=self.driver,
            gpio_pin=self.gpio_pin,
        )
