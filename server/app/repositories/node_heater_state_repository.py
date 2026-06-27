from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.node_heater_state import NodeHeaterState


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NodeHeaterStateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, node_id: str) -> NodeHeaterState | None:
        return self.db.get(NodeHeaterState, node_id)

    def get_or_create(self, node_id: str) -> NodeHeaterState:
        heater_state = self.get(node_id)

        if heater_state is None:
            heater_state = NodeHeaterState(
                node_id=node_id,
                desired_enabled=False,
                actual_enabled=False,
                updated_at=utc_now(),
            )
            self.db.add(heater_state)
            self.db.commit()
            self.db.refresh(heater_state)

        return heater_state

    def set_desired(self, node_id: str, enabled: bool) -> NodeHeaterState:
        heater_state = self.get_or_create(node_id)
        heater_state.desired_enabled = bool(enabled)
        heater_state.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(heater_state)
        return heater_state

    def update_actual(
        self,
        node_id: str,
        enabled: bool,
        driver: str | None = None,
        gpio_pin: int | None = None,
    ) -> NodeHeaterState:
        heater_state = self.get_or_create(node_id)
        heater_state.actual_enabled = bool(enabled)
        heater_state.driver = driver
        heater_state.gpio_pin = gpio_pin
        heater_state.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(heater_state)
        return heater_state
