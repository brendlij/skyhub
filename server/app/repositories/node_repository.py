from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.node import Node


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NodeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, node_id: str) -> Node | None:
        return self.db.get(Node, node_id)

    def list_all(self) -> list[Node]:
        return self.db.query(Node).order_by(Node.node_id.asc()).all()

    def delete(self, node_id: str) -> bool:
        node = self.get(node_id)

        if node is None:
            return False

        self.db.delete(node)
        self.db.commit()

        return True

    def mark_online(
        self,
        node_id: str,
        version: str | None = None,
        capabilities: dict[str, Any] | None = None,
    ) -> Node:
        node = self.get(node_id)

        if node is None:
            node = Node(node_id=node_id)
            self.db.add(node)

        now = utc_now()

        node.online = True
        node.connected_at = now
        node.disconnected_at = None
        node.last_seen_at = now
        node.last_message_type = "node.connected"

        if version is not None:
            node.version = version

        if capabilities is not None:
            node.capabilities = capabilities

        self.db.commit()
        self.db.refresh(node)

        return node

    def mark_offline(self, node_id: str) -> Node | None:
        node = self.get(node_id)

        if node is None:
            return None

        node.online = False
        node.disconnected_at = utc_now()
        node.last_message_type = "node.disconnected"

        self.db.commit()
        self.db.refresh(node)

        return node

    def update_last_seen(
        self,
        node_id: str,
        message_type: str | None = None,
        version: str | None = None,
        capabilities: dict[str, Any] | None = None,
    ) -> Node:
        node = self.get(node_id)

        if node is None:
            node = Node(node_id=node_id)
            self.db.add(node)

        node.last_seen_at = utc_now()

        if message_type is not None:
            node.last_message_type = message_type

        if version is not None:
            node.version = version

        if capabilities is not None:
            node.capabilities = capabilities

        self.db.commit()
        self.db.refresh(node)

        return node
