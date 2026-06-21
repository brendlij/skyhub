import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.camera.base import CameraInfo, CaptureResult


class PiCamera2Camera:
    def __init__(self):
        try:
            from picamera2 import Picamera2
        except ImportError as error:
            raise RuntimeError(
                "The picamera2 camera driver needs the Raspberry Pi picamera2 package. "
                "On Raspberry Pi OS, install it with: sudo apt install -y python3-picamera2"
            ) from error

        self._picamera2 = Picamera2()
        self._configured_size: tuple[int, int] | None = None
        self._started = False

    def get_info(self) -> CameraInfo:
        return CameraInfo(
            camera_id="picamera2",
            name="Raspberry Pi Camera",
            driver="picamera2",
            supports_exposure=True,
            supports_gain=True,
            supported_formats=["jpg"],
        )

    async def capture(self, settings: dict[str, Any], output_dir: Path) -> CaptureResult:
        return await asyncio.to_thread(self._capture_sync, settings, output_dir)

    def _capture_sync(self, settings: dict[str, Any], output_dir: Path) -> CaptureResult:
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"picamera2_{timestamp}_{uuid4().hex[:8]}.jpg"
        output_path = output_dir / filename

        width = int(settings.get("width", 1920))
        height = int(settings.get("height", 1080))
        exposure_ms = settings.get("exposure_ms")
        gain = settings.get("gain")
        image_format = str(settings.get("format", "jpg")).lower()

        if image_format not in ["jpg", "jpeg"]:
            raise ValueError(f"PiCamera2Camera only supports jpg for now, got: {image_format}")

        self._ensure_configured(width=width, height=height)
        self._apply_controls(exposure_ms=exposure_ms, gain=gain)

        self._picamera2.capture_file(str(output_path), format="jpeg")

        return CaptureResult(
            file_path=output_path,
            format="jpg",
            width=width,
            height=height,
            metadata={
                "captured_at": now.isoformat(),
                "camera": "picamera2",
                "exposure_ms": exposure_ms,
                "gain": gain,
            },
        )

    def _ensure_configured(self, width: int, height: int) -> None:
        size = (width, height)

        if self._started and self._configured_size == size:
            return

        if self._started:
            self._picamera2.stop()
            self._started = False

        config = self._picamera2.create_still_configuration(
            main={
                "size": size,
            }
        )
        self._picamera2.configure(config)
        self._picamera2.start()
        self._started = True
        self._configured_size = size

    def _apply_controls(self, exposure_ms: Any, gain: Any) -> None:
        controls: dict[str, Any] = {}

        if exposure_ms is not None:
            controls["ExposureTime"] = int(float(exposure_ms) * 1000)

        if gain is not None:
            controls["AnalogueGain"] = float(gain)

        if controls:
            self._picamera2.set_controls(controls)
