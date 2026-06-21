import asyncio
import json
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx
import structlog
import websockets

from app.camera.base import CameraDevice
from app.camera.factory import create_camera
from app.config import get_settings
from app.storage.paths import CAPTURES_DIR


logger = structlog.get_logger()
node_settings = get_settings()

camera: CameraDevice = create_camera(node_settings.camera_driver)
active_capture_settings: dict[str, Any] = {
    "interval_seconds": 60,
    "width": 1920,
    "height": 1080,
    "format": "jpg",
    "period": "night",
    "auto_exposure": False,
    "exposure_ms": 10000,
    "auto_gain": False,
    "gain": 8,
}
active_node_settings: dict[str, Any] = {}
active_sequence_task: asyncio.Task | None = None
active_sequence_id: str | None = None


async def send_json(websocket, message: dict[str, Any]):
    await websocket.send(json.dumps(message))


async def upload_capture(sequence_id: str, capture_result) -> dict[str, Any]:
    metadata = capture_result.metadata or {}
    form_data = {
        "node_id": node_settings.node_id,
        "sequence_id": sequence_id,
        "format": capture_result.format,
        "metadata": json.dumps(metadata),
    }

    if capture_result.width is not None:
        form_data["width"] = str(capture_result.width)

    if capture_result.height is not None:
        form_data["height"] = str(capture_result.height)

    async with httpx.AsyncClient(timeout=60, trust_env=False, verify=False) as client:
        with Path(capture_result.file_path).open("rb") as capture_file:
            response = await client.post(
                node_settings.upload_url,
                data=form_data,
                files={
                    "file": (
                        Path(capture_result.file_path).name,
                        capture_file,
                        "image/jpeg",
                    ),
                },
            )

    response.raise_for_status()
    return response.json()


async def send_hello(websocket):
    camera_info = camera.get_info()
    message = {
        "type": "node.hello",
        "node_id": node_settings.node_id,
        "version": "0.1.0",
        "capabilities": {
            "camera": camera_info.driver,
            "camera_id": camera_info.camera_id,
            "camera_name": camera_info.name,
            "supports_exposure": camera_info.supports_exposure,
            "supports_gain": camera_info.supports_gain,
            "supported_formats": camera_info.supported_formats,
            "supports_jpg": "jpg" in camera_info.supported_formats,
        },
    }

    await send_json(websocket, message)
    logger.info("node.hello.sent", node_id=node_settings.node_id)


async def heartbeat_loop(websocket):
    while True:
        message = {
            "type": "node.heartbeat",
            "node_id": node_settings.node_id,
        }

        await send_json(websocket, message)
        logger.info("node.heartbeat.sent", node_id=node_settings.node_id)

        await asyncio.sleep(node_settings.heartbeat_interval_seconds)


async def capture_sequence_loop(websocket, sequence_id: str, capture_settings: dict[str, Any]):
    interval_seconds = int(capture_settings.get("interval_seconds", 30))
    next_capture_at = asyncio.get_running_loop().time()

    logger.info(
        "sequence.loop.started",
        sequence_id=sequence_id,
        interval_seconds=interval_seconds,
        settings=capture_settings,
    )

    try:
        while True:
            now = asyncio.get_running_loop().time()

            if now < next_capture_at:
                await asyncio.sleep(next_capture_at - now)

            capture_started_at = asyncio.get_running_loop().time()
            next_capture_at = capture_started_at + interval_seconds

            await send_json(
                websocket,
                {
                    "type": "capture.started",
                    "node_id": node_settings.node_id,
                    "sequence_id": sequence_id,
                },
            )

            capture_result = await camera.capture(settings=capture_settings, output_dir=CAPTURES_DIR)

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
                    "node_id": node_settings.node_id,
                    "sequence_id": sequence_id,
                    "path": str(capture_result.file_path),
                    "format": capture_result.format,
                    "width": capture_result.width,
                    "height": capture_result.height,
                    "metadata": capture_result.metadata or {},
                },
            )

            upload_result = await upload_capture(
                sequence_id=sequence_id,
                capture_result=capture_result,
            )

            logger.info(
                "capture.uploaded",
                sequence_id=sequence_id,
                capture_id=upload_result.get("capture_id"),
                server_path=upload_result.get("path"),
            )

            await send_json(
                websocket,
                {
                    "type": "capture.uploaded",
                    "node_id": node_settings.node_id,
                    "sequence_id": sequence_id,
                    "capture_id": upload_result.get("capture_id"),
                    "server_path": upload_result.get("path"),
                    "size_bytes": upload_result.get("size_bytes"),
                },
            )

            finished_at = asyncio.get_running_loop().time()
            overrun_seconds = finished_at - next_capture_at

            if overrun_seconds > 0:
                logger.warning(
                    "capture.cadence.overrun",
                    sequence_id=sequence_id,
                    interval_seconds=interval_seconds,
                    overrun_seconds=round(overrun_seconds, 3),
                )

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
                "node_id": node_settings.node_id,
                "sequence_id": sequence_id,
                "error": str(error),
            },
        )


async def start_sequence(websocket, sequence_id: str, capture_settings: dict[str, Any]):
    global active_sequence_id, active_sequence_task

    if active_sequence_task is not None and not active_sequence_task.done():
        await stop_sequence(websocket, reason="replaced")

    effective_settings = {
        **active_capture_settings,
        **capture_settings,
    }

    await send_json(
        websocket,
        {
            "type": "sequence.started",
            "node_id": node_settings.node_id,
            "sequence_id": sequence_id,
        },
    )

    active_sequence_id = sequence_id
    active_sequence_task = asyncio.create_task(
        capture_sequence_loop(
            websocket=websocket,
            sequence_id=sequence_id,
            capture_settings=effective_settings,
        )
    )


async def apply_config_update(websocket, message: dict[str, Any]):
    global active_capture_settings, active_node_settings

    active_node_settings = message.get("settings", {}) or {}
    active_capture_settings = {
        **active_capture_settings,
        **(message.get("active_settings", {}) or {}),
    }

    logger.info(
        "config.updated",
        current_period=message.get("current_period"),
        active_settings=active_capture_settings,
    )

    await send_json(
        websocket,
        {
            "type": "config.updated",
            "node_id": node_settings.node_id,
            "current_period": message.get("current_period"),
        },
    )


async def stop_sequence(
    websocket,
    sequence_id: str | None = None,
    reason: str = "requested",
):
    global active_sequence_id, active_sequence_task

    if active_sequence_task is None or active_sequence_task.done():
        await send_json(
            websocket,
            {
                "type": "sequence.stop.ignored",
                "node_id": node_settings.node_id,
                "sequence_id": sequence_id,
                "reason": "no_active_sequence",
            },
        )
        return

    stopped_sequence_id = active_sequence_id

    if sequence_id is not None and sequence_id != active_sequence_id:
        await send_json(
            websocket,
            {
                "type": "sequence.stop.ignored",
                "node_id": node_settings.node_id,
                "sequence_id": sequence_id,
                "active_sequence_id": active_sequence_id,
                "reason": "sequence_id_mismatch",
            },
        )
        return

    active_sequence_task.cancel()

    with suppress(asyncio.CancelledError):
        await active_sequence_task

    active_sequence_task = None
    active_sequence_id = None

    await send_json(
        websocket,
        {
            "type": "sequence.stopped",
            "node_id": node_settings.node_id,
            "sequence_id": stopped_sequence_id,
            "reason": reason,
        },
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
            capture_settings = message.get("settings", {})

            if not sequence_id:
                logger.warning("sequence.start.invalid", reason="missing_sequence_id")
                continue

            logger.info(
                "sequence.start.received",
                sequence_id=sequence_id,
                settings=capture_settings,
            )

            await start_sequence(
                websocket=websocket,
                sequence_id=sequence_id,
                capture_settings=capture_settings,
            )

        elif message_type == "sequence.stop":
            await stop_sequence(
                websocket=websocket,
                sequence_id=message.get("sequence_id"),
            )

        elif message_type == "config.update":
            await apply_config_update(websocket=websocket, message=message)


async def cancel_active_sequence(reason: str):
    global active_sequence_id, active_sequence_task

    if active_sequence_task is None or active_sequence_task.done():
        active_sequence_task = None
        active_sequence_id = None
        return

    logger.warning(
        "sequence.local.cancelled",
        sequence_id=active_sequence_id,
        reason=reason,
    )

    active_sequence_task.cancel()

    with suppress(asyncio.CancelledError):
        await active_sequence_task

    active_sequence_task = None
    active_sequence_id = None


async def run_connection():
    logger.info(
        "node.connecting",
        node_id=node_settings.node_id,
        server_url=node_settings.server_ws_url,
    )

    async with websockets.connect(node_settings.server_ws_url) as websocket:
        logger.info("node.connected", node_id=node_settings.node_id)

        await send_hello(websocket)

        try:
            heartbeat_task = asyncio.create_task(heartbeat_loop(websocket))
            receive_task = asyncio.create_task(receive_loop(websocket))
            tasks = {heartbeat_task, receive_task}

            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

            for task in pending:
                task.cancel()

            for task in pending:
                with suppress(asyncio.CancelledError):
                    await task

            for task in done:
                task.result()

        finally:
            await cancel_active_sequence(reason="connection_lost")


async def main():
    reconnect_delay = node_settings.reconnect_initial_delay_seconds

    logger.info(
        "node.starting",
        node_id=node_settings.node_id,
        server_url=node_settings.server_ws_url,
    )

    while True:
        try:
            await run_connection()
            logger.warning(
                "node.connection.closed",
                node_id=node_settings.node_id,
                reconnect_delay_seconds=reconnect_delay,
            )
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = node_settings.reconnect_initial_delay_seconds

        except Exception as error:
            logger.warning(
                "node.connection.lost",
                node_id=node_settings.node_id,
                error=str(error),
                reconnect_delay_seconds=reconnect_delay,
            )

            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(
                reconnect_delay * 2,
                node_settings.reconnect_max_delay_seconds,
            )


if __name__ == "__main__":
    asyncio.run(main())
