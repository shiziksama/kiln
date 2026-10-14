from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
PHOTOS_DIR = BASE_DIR / "photos"

DEFAULT_VIDEO_PATH = PHOTOS_DIR / "document_5384427076805764565.mp4"
DISPLAY_CROP_PATH = STATIC_DIR / "latest-display.jpg"

COLLECT_INTERVAL_SECONDS = 3.0
def parse_roi(name: str, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    value = os.getenv(name)
    if not value:
        return default
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        return default
    try:
        return tuple(int(part) for part in parts)  # type: ignore[return-value]
    except ValueError:
        return default
