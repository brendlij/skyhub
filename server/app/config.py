from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


SERVER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_DIR.parent


class ServerSettings(BaseSettings):
    app_name: str = "SkyHub Server"
    app_version: str = "0.1.0"
    data_dir: Path = REPO_ROOT / "data"
    database_filename: str = "skyhub.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SKYHUB_SERVER_",
    )

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database_filename


@lru_cache
def get_settings() -> ServerSettings:
    return ServerSettings()
