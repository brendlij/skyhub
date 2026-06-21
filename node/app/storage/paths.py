from app.config import get_settings

settings = get_settings()
CAPTURES_DIR = settings.captures_dir

CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
