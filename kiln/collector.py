import threading
import time
import json
import os
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2

from kiln.sensors import DHTSensor
from kiln.vision import crop_display, read_kiln_temperature


OCR_BURST_FRAMES = 12


@dataclass(slots=True)
class Reading:
    timestamp: str
    ambient_temperature: float | None
    humidity: float | None
    kiln_temperature: float | None
    source: str


class Collector:
    def __init__(
        self,
        *,
        interval_seconds: float,
        display_crop_path: Path,
        display_roi: tuple[int, int, int, int],
        digits_roi: tuple[int, int, int, int],
        video_path: Path | None = None,
        camera_index: int | None = None,
        camera_backend: str = "v4l2",
        camera_fourcc: str = "MJPG",
        camera_width: int = 1280,
        camera_height: int = 720,
        camera_fps: int = 30,
        camera_warmup_seconds: float = 3.0,
    ) -> None:
        self.interval_seconds = interval_seconds
        self.display_crop_path = display_crop_path
        self.display_roi = display_roi
        self.digits_roi = digits_roi
        self.video_path = video_path
        self.camera_index = camera_index
        self.camera_backend = camera_backend
        self.camera_fourcc = camera_fourcc
        self.camera_width = camera_width
        self.camera_height = camera_height
        self.camera_fps = camera_fps
        self.camera_warmup_seconds = camera_warmup_seconds
        self.sensor = DHTSensor()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: cv2.VideoCapture | None = None
        self._remote_url = os.getenv("KILN_REMOTE_URL", "").strip()
        self._remote_interval = max(1.0, float(os.getenv("KILN_REMOTE_INTERVAL", "10")))
        self._last_remote_send = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _run(self) -> None:
        self._capture = self._open_capture()
        camera_available = self._capture is not None and self._capture.isOpened()
        if not camera_available:
            print("Camera unavailable; continuing with ambient sensor readings", flush=True)
            if self._capture is not None:
                self._capture.release()
                self._capture = None

        while not self._stop.is_set():
            frames = []
            if camera_available and self._capture is not None:
                for _ in range(OCR_BURST_FRAMES):
                    ok, frame = self._capture.read()
                    if not ok or frame is None:
                        if self.video_path is not None:
                            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        break
                    frames.append(frame)

            ambient_temperature, humidity = self.sensor.read()
            if not frames:
                kiln_temperature = None
            else:
                display = crop_display(frames[-1], self.display_roi)
                cv2.imwrite(str(self.display_crop_path), display)
                readings = [
                    value
                    for frame in frames
                    if (value := read_kiln_temperature(
                        frame,
                        display_roi=self.display_roi,
                        digits_roi=self.digits_roi,
                    )) is not None
                ]
                kiln_temperature = Counter(readings).most_common(1)[0][0] if readings else None
            reading = Reading(
                timestamp=datetime.now(timezone.utc).isoformat(),
                ambient_temperature=ambient_temperature,
                humidity=humidity,
                kiln_temperature=kiln_temperature,
                source=(
                    "video"
                    if self.video_path is not None and camera_available
                    else "camera"
                    if camera_available
                    else "sensor-only"
                ),
            )
            self._send_remote_if_due(reading)
            time.sleep(self.interval_seconds)

    def _send_remote_if_due(self, reading) -> None:
        if not self._remote_url:
            return
        now = time.monotonic()
        if now - self._last_remote_send < self._remote_interval:
            return
        payload = {
            "timestamp": reading.timestamp,
            "ambient_temperature": reading.ambient_temperature,
            "humidity": reading.humidity,
            "kiln_temperature": reading.kiln_temperature,
            "source": reading.source,
        }
        headers = {"Content-Type": "application/json"}
        request = urllib.request.Request(
            self._remote_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        self._last_remote_send = now
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status != 200:
                    print(f"Remote reading upload returned HTTP {response.status}", flush=True)
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            print(f"Remote reading upload failed: {error}", flush=True)

    def _open_capture(self) -> cv2.VideoCapture | None:
        if self.video_path is not None:
            return cv2.VideoCapture(str(self.video_path))

        backend = cv2.CAP_V4L2 if self.camera_backend == "v4l2" else cv2.CAP_ANY
        capture = cv2.VideoCapture(self.camera_index or 0, backend)
        if self.camera_fourcc:
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.camera_fourcc[:4]))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
        capture.set(cv2.CAP_PROP_FPS, self.camera_fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        deadline = time.monotonic() + self.camera_warmup_seconds
        while time.monotonic() < deadline:
            capture.read()
        return capture
