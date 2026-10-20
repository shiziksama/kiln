import os
import signal
import threading
from pathlib import Path

from kiln.collector import Collector
from kiln.settings import (
    COLLECT_INTERVAL_SECONDS,
    DEFAULT_VIDEO_PATH,
    DISPLAY_CROP_PATH,
    parse_roi,
)
from kiln.vision import DEFAULT_DIGITS_ROI, DEFAULT_DISPLAY_ROI


def main() -> None:
    stop_event = threading.Event()
    signal.signal(signal.SIGINT, lambda _signum, _frame: stop_event.set())
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stop_event.set())

    source = os.getenv("KILN_SOURCE", "camera")
    video_path = Path(os.getenv("KILN_VIDEO_PATH", str(DEFAULT_VIDEO_PATH)))
    camera_device = os.getenv("KILN_CAMERA_INDEX", "0")
    camera_device = int(camera_device) if camera_device.isdecimal() else camera_device
    collector = Collector(
        interval_seconds=float(os.getenv("KILN_INTERVAL", str(COLLECT_INTERVAL_SECONDS))),
        display_crop_path=DISPLAY_CROP_PATH,
        display_roi=parse_roi("KILN_DISPLAY_ROI", DEFAULT_DISPLAY_ROI),
        digits_roi=parse_roi("KILN_DIGITS_ROI", DEFAULT_DIGITS_ROI),
        video_path=video_path if source == "video" else None,
        camera_index=camera_device if source == "camera" else None,
        camera_backend=os.getenv("KILN_CAMERA_BACKEND", "v4l2"),
        camera_fourcc=os.getenv("KILN_CAMERA_FOURCC", "MJPG"),
        camera_width=int(os.getenv("KILN_CAMERA_WIDTH", "1280")),
        camera_height=int(os.getenv("KILN_CAMERA_HEIGHT", "720")),
        camera_fps=int(os.getenv("KILN_CAMERA_FPS", "30")),
        camera_warmup_seconds=float(os.getenv("KILN_CAMERA_WARMUP_SECONDS", "3")),
    )

    collector.start()
    try:
        while not stop_event.wait(1):
            if not collector.is_running:
                raise RuntimeError("Collector stopped unexpectedly")
    finally:
        collector.stop()


if __name__ == "__main__":
    main()
