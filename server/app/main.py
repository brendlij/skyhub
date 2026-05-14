from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import structlog

from app.db.database import SessionLocal, create_db_tables, get_db_session
from app.repositories.node_repository import NodeRepository
from app.realtime.connection_manager import ConnectionManager

logger = structlog.get_logger()
connections = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_tables()
    logger.info("database.ready")
    yield


app = FastAPI(
    title="SkyHub Server",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/nodes")
async def list_nodes(db: Session = Depends(get_db_session)):
    repo = NodeRepository(db)
    nodes = repo.list_all()

    return {
        "nodes": [
            {
                "node_id": node.node_id,
                "online": node.online,
                "version": node.version,
                "capabilities": node.capabilities,
                "connected_at": node.connected_at.isoformat() if node.connected_at else None,
                "disconnected_at": node.disconnected_at.isoformat() if node.disconnected_at else None,
                "last_seen_at": node.last_seen_at.isoformat() if node.last_seen_at else None,
                "last_message_type": node.last_message_type,
            }
            for node in nodes
        ]
    }


@app.websocket("/ws/nodes/{node_id}")
async def node_websocket(websocket: WebSocket, node_id: str):
    await connections.connect(node_id, websocket)

    db = SessionLocal()
    repo = NodeRepository(db)

    try:
        repo.mark_online(node_id)
        logger.info("node.connected", node_id=node_id)

        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            version = None
            capabilities = None

            if message_type == "node.hello":
                version = message.get("version")
                capabilities = message.get("capabilities", {})

            repo.update_last_seen(
                node_id=node_id,
                message_type=message_type,
                version=version,
                capabilities=capabilities,
            )

            connections.update_last_seen(
                node_id=node_id,
                message_type=message_type,
                metadata={
                    "version": version,
                    "capabilities": capabilities,
                }
                if message_type == "node.hello"
                else None,
            )

            logger.info(
                "node.message.received",
                node_id=node_id,
                message_type=message_type,
            )

            await websocket.send_json(
                {
                    "type": "server.ack",
                    "received_type": message_type,
                }
            )

    except WebSocketDisconnect:
        connections.disconnect(node_id)
        repo.mark_offline(node_id)
        logger.warning("node.disconnected", node_id=node_id)

    finally:
        db.close()