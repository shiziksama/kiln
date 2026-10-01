import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kiln.collector import Collector
from kiln.settings import (
    COLLECT_INTERVAL_SECONDS,
    DEFAULT_VIDEO_PATH,
    DISPLAY_CROP_PATH,
    LEGACY_READINGS_CSV_PATH,
    MAX_READINGS,
    READINGS_DB_PATH,
    STATIC_DIR,
    parse_roi,
)
from kiln.storage import ReadingStore
from kiln.vision import DEFAULT_DIGITS_ROI, DEFAULT_DISPLAY_ROI


store = ReadingStore(READINGS_DB_PATH, MAX_READINGS, csv_import_path=LEGACY_READINGS_CSV_PATH)
collector: Collector | None = None
app = FastAPI(title="Kiln Monitor")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def startup() -> None:
    global collector
    source = os.getenv("KILN_SOURCE", "video")
    video_path = Path(os.getenv("KILN_VIDEO_PATH", str(DEFAULT_VIDEO_PATH)))
    camera_index = int(os.getenv("KILN_CAMERA_INDEX", "0"))
    display_roi = parse_roi("KILN_DISPLAY_ROI", DEFAULT_DISPLAY_ROI)
    digits_roi = parse_roi("KILN_DIGITS_ROI", DEFAULT_DIGITS_ROI)
    collector = Collector(
        store=store,
        interval_seconds=float(os.getenv("KILN_INTERVAL", str(COLLECT_INTERVAL_SECONDS))),
        display_crop_path=DISPLAY_CROP_PATH,
        display_roi=display_roi,
        digits_roi=digits_roi,
        max_temperature_step=float(os.getenv("KILN_MAX_STEP", "15")),
        confirmation_tolerance=float(os.getenv("KILN_CONFIRMATION_TOLERANCE", "3")),
        video_path=video_path if source == "video" else None,
        camera_index=camera_index if source == "camera" else None,
        camera_backend=os.getenv("KILN_CAMERA_BACKEND", "v4l2"),
        camera_fourcc=os.getenv("KILN_CAMERA_FOURCC", "MJPG"),
        camera_width=int(os.getenv("KILN_CAMERA_WIDTH", "1280")),
        camera_height=int(os.getenv("KILN_CAMERA_HEIGHT", "720")),
        camera_fps=int(os.getenv("KILN_CAMERA_FPS", "30")),
    )
    collector.start()


@app.on_event("shutdown")
def shutdown() -> None:
    if collector is not None:
        collector.stop()
    store.close()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/readings")
def readings() -> list[dict]:
    return [asdict(reading) for reading in store.all()]


@app.get("/api/readings/minutely")
def minutely_readings() -> list[dict]:
    return [asdict(reading) for reading in store.minutely()]


@app.get("/api/latest")
def latest() -> dict | None:
    reading = store.latest()
    return asdict(reading) if reading else None


@app.get("/api/config")
def config() -> dict:
    return {
        "display_roi": parse_roi("KILN_DISPLAY_ROI", DEFAULT_DISPLAY_ROI),
        "digits_roi": parse_roi("KILN_DIGITS_ROI", DEFAULT_DIGITS_ROI),
        "interval_seconds": float(os.getenv("KILN_INTERVAL", str(COLLECT_INTERVAL_SECONDS))),
        "max_temperature_step": float(os.getenv("KILN_MAX_STEP", "15")),
        "confirmation_tolerance": float(os.getenv("KILN_CONFIRMATION_TOLERANCE", "3")),
        "camera_backend": os.getenv("KILN_CAMERA_BACKEND", "v4l2"),
        "camera_fourcc": os.getenv("KILN_CAMERA_FOURCC", "MJPG"),
        "camera_width": int(os.getenv("KILN_CAMERA_WIDTH", "1280")),
        "camera_height": int(os.getenv("KILN_CAMERA_HEIGHT", "720")),
        "camera_fps": int(os.getenv("KILN_CAMERA_FPS", "30")),
    }
