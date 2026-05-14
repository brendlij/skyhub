from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass
class CameraInfo:
    camera_id: str
    name: str
    driver: str
    supports_exposure: bool
    supports_gain: bool
    supported_formats: list[str]


@dataclass
class CaptureResult:
    file_path: Path
    format: str
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] | None = None


class CameraDevice(Protocol):
    def get_info(self) -> CameraInfo:
        ...

    async def capture(
        self,
        settings: dict[str, Any],
        output_dir: Path,
    ) -> CaptureResult:
        ...