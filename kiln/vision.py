import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


DEFAULT_DISPLAY_ROI = (510, 225, 110, 65)
DEFAULT_DIGITS_ROI = (23, 17, 66, 32)
TESSDATA_DIR = Path(__file__).resolve().parent.parent / "models" / "tessdata"


def read_kiln_temperature(
    frame: np.ndarray,
    crop_path: Path | None = None,
    display_roi: tuple[int, int, int, int] = DEFAULT_DISPLAY_ROI,
    digits_roi: tuple[int, int, int, int] = DEFAULT_DIGITS_ROI,
) -> float | None:
    display, digits = extract_display(frame, display_roi, digits_roi)
    if display.size == 0:
        return None
    if crop_path is not None:
        crop_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(crop_path), display)

    if digits.size == 0:
        return None
    text = _read_with_tesseract(digits)
    # All three positions must be read, including leading zeroes. A truncated
    # result such as '02' from '025' must never become a temperature of 2.
    expected_digits = int(os.getenv("KILN_OCR_DIGITS", "3"))
    if len(text.replace(".", "")) != expected_digits:
        return None
    value = _parse_number(text)
    return value if _is_plausible_temperature(value) else None


def crop_display(
    frame: np.ndarray, display_roi: tuple[int, int, int, int] = DEFAULT_DISPLAY_ROI
) -> np.ndarray:
    x, y, w, h = display_roi
    return frame[y : y + h, x : x + w]


def crop_digits(
    display: np.ndarray, digits_roi: tuple[int, int, int, int] = DEFAULT_DIGITS_ROI
) -> np.ndarray:
    x, y, w, h = digits_roi
    return display[y : y + h, x : x + w]


def find_display_roi(
    frame: np.ndarray, expected_roi=DEFAULT_DISPLAY_ROI,
) -> tuple[int, int, int, int] | None:
    """Locate the red display cover; digit recognition remains in Tesseract."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 80, 100), (15, 255, 255))
    mask |= cv2.inRange(hsv, (165, 80, 100), (180, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if w >= 32 and h >= 15 and 1.5 < w / h < 4 and area > 300 and area / (w * h) > 0.4:
            candidates.append((area, (x, y, w, h)))
    if not candidates:
        return None
    ex, ey, ew, eh = expected_roi
    center_x, center_y = ex + ew / 2, ey + eh / 2
    # Red objects elsewhere in the workshop can be larger than the display.
    # Prefer the panel nearest its calibrated position instead of the largest.
    return min(candidates, key=lambda item: (
        (item[1][0] + item[1][2] / 2 - center_x) ** 2
        + (item[1][1] + item[1][3] / 2 - center_y) ** 2
    ))[1]


def extract_display(frame, display_roi=DEFAULT_DISPLAY_ROI, digits_roi=DEFAULT_DIGITS_ROI):
    if os.getenv("KILN_AUTO_DISPLAY", "1") == "1":
        located = find_display_roi(frame, display_roi)
        if located is None:
            # Never OCR an unrelated patch when the display cannot be located.
            return frame[:0, :0], frame[:0, :0]
        display = crop_display(frame, located)
        return display, display[2:-2, 2:-2]
    display = crop_display(frame, display_roi)
    return display, crop_digits(display, digits_roi)


def _read_with_tesseract(image: np.ndarray) -> str:
    processed = _prepare_for_ocr(image)
    votes: Counter[float] = Counter()
    texts: dict[float, str] = {}
    for psm in (7, 13, 8):
        text = _run_tesseract(processed, psm)
        if len(text.replace(".", "")) != int(os.getenv("KILN_OCR_DIGITS", "3")):
            continue
        value = _parse_number(text)
        if value is not None:
            votes[value] += 1
            texts[value] = text
            if votes[value] >= 2:
                return text
    # A complete reading can survive modes that return nothing/truncated text;
    # the burst still needs a strict majority of frames before publishing it.
    if len(votes) == 1:
        value = next(iter(votes))
        return texts[value]
    return ""


def _run_tesseract(processed: np.ndarray, psm: int = 7) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png") as src:
        cv2.imwrite(src.name, processed)
        try:
            result = subprocess.run(
                [
                    "tesseract", src.name, "stdout",
                    "--tessdata-dir", str(TESSDATA_DIR),
                    "-l", "display", "--psm", str(psm),
                    "-c", "tessedit_char_whitelist=0123456789.",
                ],
                check=False, capture_output=True, text=True, timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _prepare_for_ocr(image: np.ndarray, channel: str | None = None) -> np.ndarray:
    # The red cover saturates R; G retains the contrast of the white digit cores.
    channel = channel or os.getenv("KILN_OCR_CHANNEL", "green")
    channels = {"blue": 0, "green": 1, "red": 2}
    if channel == "gray":
        plane = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif channel in channels:
        plane = image[:, :, channels[channel]]
    else:
        raise ValueError(f"Unknown OCR channel: {channel}")
    plane = cv2.resize(plane, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    _, mask = cv2.threshold(plane, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return cv2.copyMakeBorder(mask, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)


def _parse_number(text: str) -> float | None:
    cleaned = text.strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]*)?", cleaned):
        return None
    return float(cleaned)


def _is_plausible_temperature(value: float | None) -> bool:
    return value is not None and 0 <= value <= 999
