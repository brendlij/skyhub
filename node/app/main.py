import asyncio
import json

import structlog
import websockets

NODE_ID = "pi-hqcam-01"
SERVER_WS_URL = f"ws://127.0.0.1:8000/ws/nodes/{NODE_ID}"

logger = structlog.get_logger()


async def send_hello(websocket):
    message = {
        "type": "node.hello",
        "node_id": NODE_ID,
        "version": "0.1.0",
        "capabilities": {
            "camera": "mock",
            "supports_exposure": True,
            "supports_gain": True,
            "supports_jpg": True,
        },
    }

    await websocket.send(json.dumps(message))
    logger.info("node.hello.sent", node_id=NODE_ID)


async def send_heartbeat(websocket):
    message = {
        "type": "node.heartbeat",
        "node_id": NODE_ID,
    }

    await websocket.send(json.dumps(message))
    logger.info("node.heartbeat.sent", node_id=NODE_ID)


async def main():
    logger.info("node.starting", node_id=NODE_ID, server_url=SERVER_WS_URL)

    async with websockets.connect(SERVER_WS_URL) as websocket:
        logger.info("node.connected", node_id=NODE_ID)

        await send_hello(websocket)

        while True:
            await send_heartbeat(websocket)

            response = await websocket.recv()
            logger.info("server.message.received", message=response)

            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())