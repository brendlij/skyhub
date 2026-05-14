import asyncio
import json
from pathlib import Path
from typing import Any

import structlog
import websockets

from app.camera.mock_camera import MockCamera
from app.storage.paths import CAPTURES_DIR
from app.camera.base import CameraDevice
from app.camera.mock_camera import MockCamera


NODE_ID = "pi-hqcam-01"
SERVER_WS_URL = f"ws://127.0.0.1:8000/ws/nodes/{NODE_ID}"

logger = structlog.get_logger()

camera: CameraDevice = MockCamera()
active_sequence_task: asyncio.Task | None = None


async def send_json(websocket, message: dict[str, Any]):
    await websocket.send(json.dumps(message))


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

    await send_json(websocket, message)
    logger.info("node.hello.sent", node_id=NODE_ID)


async def heartbeat_loop(websocket):
    while True:
        message = {
            "type": "node.heartbeat",
            "node_id": NODE_ID,
        }

        await send_json(websocket, message)
        logger.info("node.heartbeat.sent", node_id=NODE_ID)

        await asyncio.sleep(10)


async def capture_sequence_loop(websocket, sequence_id: str, settings: dict[str, Any]):
    interval_seconds = int(settings.get("interval_seconds", 30))

    logger.info(
        "sequence.loop.started",
        sequence_id=sequence_id,
        interval_seconds=interval_seconds,
        settings=settings,
    )

    try:
        while True:
            await send_json(
                websocket,
                {
                    "type": "capture.started",
                    "node_id": NODE_ID,
                    "sequence_id": sequence_id,
                },
            )

            capture_result = await camera.capture(settings=settings, output_dir=CAPTURES_DIR)

            logger.info(
                "capture.saved.local",
                sequence_id=sequence_id,
                path=str(capture_result.file_path),
                format=capture_result.format,
                width=capture_result.width,
                height=capture_result.height,
            )

            await send_json(
                websocket,
                {
                    "type": "capture.saved.local",
                    "node_id": NODE_ID,
                    "sequence_id": sequence_id,
                    "path": str(capture_result.file_path),
                    "format": capture_result.format,
                    "width": capture_result.width,
                    "height": capture_result.height,
                    "metadata": capture_result.metadata or {},
                },
            )

            await asyncio.sleep(interval_seconds)

    except asyncio.CancelledError:
        logger.warning("sequence.loop.cancelled", sequence_id=sequence_id)
        raise

    except Exception as error:
        logger.exception(
            "sequence.loop.failed",
            sequence_id=sequence_id,
            error=str(error),
        )

        await send_json(
            websocket,
            {
                "type": "sequence.failed",
                "node_id": NODE_ID,
                "sequence_id": sequence_id,
                "error": str(error),
            },
        )


async def start_sequence(websocket, sequence_id: str, settings: dict[str, Any]):
    global active_sequence_task

    if active_sequence_task is not None and not active_sequence_task.done():
        active_sequence_task.cancel()

    await send_json(
        websocket,
        {
            "type": "sequence.started",
            "node_id": NODE_ID,
            "sequence_id": sequence_id,
        },
    )

    active_sequence_task = asyncio.create_task(
        capture_sequence_loop(
            websocket=websocket,
            sequence_id=sequence_id,
            settings=settings,
        )
    )


async def receive_loop(websocket):
    async for raw_message in websocket:
        message = json.loads(raw_message)
        message_type = message.get("type")

        logger.info(
            "server.message.received",
            message_type=message_type,
            message=message,
        )

        if message_type == "sequence.start":
            sequence_id = message.get("sequence_id")
            settings = message.get("settings", {})

            if not sequence_id:
                logger.warning("sequence.start.invalid", reason="missing_sequence_id")
                continue

            logger.info(
                "sequence.start.received",
                sequence_id=sequence_id,
                settings=settings,
            )

            await start_sequence(
                websocket=websocket,
                sequence_id=sequence_id,
                settings=settings,
            )


async def main():
    logger.info("node.starting", node_id=NODE_ID, server_url=SERVER_WS_URL)

    async with websockets.connect(SERVER_WS_URL) as websocket:
        logger.info("node.connected", node_id=NODE_ID)

        await send_hello(websocket)

        await asyncio.gather(
            heartbeat_loop(websocket),
            receive_loop(websocket),
        )


if __name__ == "__main__":
    asyncio.run(main())