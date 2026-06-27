from app.heater.base import HeaterController, HeaterState


class GpiozeroHeaterController(HeaterController):
    driver = "gpiozero"

    def __init__(self, gpio_pin: int, active_high: bool = True):
        try:
            from gpiozero import DigitalOutputDevice
        except ImportError as error:
            raise RuntimeError("gpiozero is required for GPIO heater support") from error

        self.gpio_pin = gpio_pin
        self.device = DigitalOutputDevice(
            pin=gpio_pin,
            active_high=active_high,
            initial_value=False,
        )

    def set_enabled(self, enabled: bool) -> HeaterState:
        if enabled:
            self.device.on()
        else:
            self.device.off()

        return self.get_state()

    def get_state(self) -> HeaterState:
        return HeaterState(
            enabled=bool(self.device.value),
            driver=self.driver,
            gpio_pin=self.gpio_pin,
        )

    def close(self) -> None:
        self.device.close()
