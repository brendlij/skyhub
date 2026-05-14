from pathlib import Path

NODE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = NODE_DIR / "data"
CAPTURES_DIR = DATA_DIR / "captures"

CAPTURES_DIR.mkdir(parents=True, exist_ok=True)