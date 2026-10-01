import threading
import time
from pathlib import Path

import cv2

from kiln.sensors import DHTSensor
from kiln.storage import ReadingStore
from kiln.vision import read_kiln_temperature


class Collector:
    def __init__(
        self,
        *,
        store: ReadingStore,
        interval_seconds: float,
        display_crop_path: Path,
        display_roi: tuple[int, int, int, int],
        digits_roi: tuple[int, int, int, int],
        max_temperature_step: float,
        confirmation_tolerance: float,
        video_path: Path | None = None,
        camera_index: int | None = None,
        camera_backend: str = "v4l2",
        camera_fourcc: str = "MJPG",
        camera_width: int = 1280,
        camera_height: int = 720,
        camera_fps: int = 30,
        camera_warmup_seconds: float = 3.0,
    ) -> None:
        self.store = store
        self.interval_seconds = interval_seconds
        self.display_crop_path = display_crop_path
        self.display_roi = display_roi
        self.digits_roi = digits_roi
        self.max_temperature_step = max_temperature_step
        self.confirmation_tolerance = confirmation_tolerance
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
        self._last_kiln_temperature: float | None = None
        self._pending_kiln_temperature: float | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _run(self) -> None:
        self._capture = self._open_capture()
        if self._capture is None or not self._capture.isOpened():
            return

        while not self._stop.is_set():
            ok, frame = self._capture.read()
            if not ok:
                if self.video_path is not None:
                    self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                time.sleep(self.interval_seconds)
                continue

            ambient_temperature, humidity = self.sensor.read()
            raw_kiln_temperature = read_kiln_temperature(
                frame,
                self.display_crop_path,
                display_roi=self.display_roi,
                digits_roi=self.digits_roi,
            )
            kiln_temperature = self._stabilize_kiln_temperature(raw_kiln_temperature)
            self.store.add(
                ambient_temperature=ambient_temperature,
                humidity=humidity,
                kiln_temperature=kiln_temperature,
                source="video" if self.video_path is not None else "camera",
            )
            time.sleep(self.interval_seconds)

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
        deadline = time.monotonic() + self.camera_warmup_seconds
        while time.monotonic() < deadline:
            capture.read()
        return capture

    def _stabilize_kiln_temperature(self, value: float | None) -> float | None:
        if value is None:
            return self._last_kiln_temperature

        if self._last_kiln_temperature is not None:
            if abs(value - self._last_kiln_temperature) <= self.max_temperature_step:
                self._last_kiln_temperature = value
                self._pending_kiln_temperature = None
            return self._last_kiln_temperature

        if self._pending_kiln_temperature is None:
            self._pending_kiln_temperature = value
            return None

        if abs(value - self._pending_kiln_temperature) <= self.confirmation_tolerance:
            self._last_kiln_temperature = value
            self._pending_kiln_temperature = None
            return self._last_kiln_temperature

        self._pending_kiln_temperature = value
        return None
