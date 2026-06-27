from dataclasses import dataclass


@dataclass
class HeaterState:
    enabled: bool
    driver: str
    gpio_pin: int | None = None


class HeaterController:
    driver: str = "base"
    gpio_pin: int | None = None

    def set_enabled(self, enabled: bool) -> HeaterState:
        raise NotImplementedError

    def get_state(self) -> HeaterState:
        raise NotImplementedError

    def close(self) -> None:
        pass
