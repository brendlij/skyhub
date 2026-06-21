from app.camera.base import CameraDevice
from app.camera.mock_camera import MockCamera


def create_camera(driver: str) -> CameraDevice:
    normalized_driver = driver.strip().lower()

    if normalized_driver == "mock":
        return MockCamera()

    if normalized_driver == "picamera2":
        from app.camera.picamera2_camera import PiCamera2Camera

        return PiCamera2Camera()

    raise ValueError(
        f"Unsupported camera driver '{driver}'. "
        "Supported drivers: mock, picamera2."
    )
