from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.node_environment import NodeEnvironment


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NodeEnvironmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, node_id: str) -> NodeEnvironment | None:
        return self.db.get(NodeEnvironment, node_id)

    def upsert(
        self,
        node_id: str,
        sensor_driver: str | None,
        temperature_c: float,
        humidity_percent: float,
        pressure_hpa: float | None = None,
        dew_point_c: float | None = None,
        captured_at: datetime | None = None,
    ) -> NodeEnvironment:
        environment = self.get(node_id)

        if environment is None:
            environment = NodeEnvironment(node_id=node_id)
            self.db.add(environment)

        environment.sensor_driver = sensor_driver
        environment.temperature_c = temperature_c
        environment.humidity_percent = humidity_percent
        environment.pressure_hpa = pressure_hpa
        environment.dew_point_c = dew_point_c
        environment.captured_at = captured_at
        environment.updated_at = utc_now()

        self.db.commit()
        self.db.refresh(environment)

        return environment
