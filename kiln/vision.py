import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


DEFAULT_DISPLAY_ROI = (220, 560, 315, 175)
DEFAULT_DIGITS_ROI = (90, 30, 210, 110)


def read_kiln_temperature(
    frame: np.ndarray,
    crop_path: Path | None = None,
    display_roi: tuple[int, int, int, int] = DEFAULT_DISPLAY_ROI,
    digits_roi: tuple[int, int, int, int] = DEFAULT_DIGITS_ROI,
) -> float | None:
    display = crop_display(frame, display_roi)
    if crop_path is not None:
        crop_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(crop_path), display)

    digits = crop_digits(display, digits_roi)
    text = _read_with_tesseract(digits)
    value = _parse_number(text)
    if _is_plausible_temperature(value):
        return value
    value = _read_seven_segment(digits)
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


def _read_with_tesseract(image: np.ndarray) -> str:
    processed = _prepare_for_ocr(image)
    with tempfile.NamedTemporaryFile(suffix=".png") as src:
        cv2.imwrite(src.name, processed)
        result = subprocess.run(
            [
                "tesseract",
                src.name,
                "stdout",
                "--psm",
                "8",
                "-c",
                "tessedit_char_whitelist=0123456789.",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _prepare_for_ocr(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv[:, :, 2], 210, 255)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    mask = cv2.copyMakeBorder(mask, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=0)
    return mask


def _parse_number(text: str) -> float | None:
    cleaned = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_plausible_temperature(value: float | None) -> bool:
    return value is not None and 20 <= value <= 999


def _read_seven_segment(image: np.ndarray) -> float | None:
    mask = _segment_mask(image)
    columns = np.where(mask.any(axis=0))[0]
    if len(columns) == 0:
        return None

    groups = _column_groups(columns)
    groups = [group for group in groups if group[1] - group[0] >= 12]
    digits: list[str] = []
    for start, end in groups:
        digit_mask = mask[:, max(0, start - 2) : min(mask.shape[1], end + 3)]
        digit = _classify_digit(digit_mask)
        if digit is not None:
            digits.append(digit)

    if not digits:
        return None
    return float("".join(digits))


def _segment_mask(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red = cv2.inRange(hsv, (0, 35, 110), (12, 255, 255))
    red |= cv2.inRange(hsv, (165, 35, 110), (180, 255, 255))
    bright = cv2.inRange(hsv[:, :, 2], 175, 255)
    mask = cv2.bitwise_or(red, bright)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return mask > 0


def _column_groups(columns: np.ndarray) -> list[tuple[int, int]]:
    groups: list[tuple[int, int]] = []
    start = int(columns[0])
    previous = int(columns[0])
    for column in columns[1:]:
        column = int(column)
        if column - previous > 8:
            groups.append((start, previous))
            start = column
        previous = column
    groups.append((start, previous))
    return groups


def _classify_digit(mask: np.ndarray) -> str | None:
    h, w = mask.shape
    if h < 20 or w < 10:
        return None

    zones = {
        "a": mask[0 : h // 5, w // 4 : 3 * w // 4],
        "b": mask[h // 8 : h // 2, 2 * w // 3 : w],
        "c": mask[h // 2 : 7 * h // 8, 2 * w // 3 : w],
        "d": mask[4 * h // 5 : h, w // 4 : 3 * w // 4],
        "e": mask[h // 2 : 7 * h // 8, 0 : w // 3],
        "f": mask[h // 8 : h // 2, 0 : w // 3],
        "g": mask[2 * h // 5 : 3 * h // 5, w // 4 : 3 * w // 4],
    }
    active = frozenset(name for name, zone in zones.items() if zone.mean() > 0.08)
    patterns = {
        frozenset("abcdef"): "0",
        frozenset("bc"): "1",
        frozenset("abged"): "2",
        frozenset("abgcd"): "3",
        frozenset("fgbc"): "4",
        frozenset("afgcd"): "5",
        frozenset("afgecd"): "6",
        frozenset("abc"): "7",
        frozenset("abcdefg"): "8",
        frozenset("abfgcd"): "9",
    }
    if active in patterns:
        return patterns[active]
    return _closest_pattern(active, patterns)


def _closest_pattern(active: frozenset[str], patterns: dict[frozenset[str], str]) -> str | None:
    best_digit = None
    best_score = 10
    for pattern, digit in patterns.items():
        score = len(active ^ pattern)
        if score < best_score:
            best_score = score
            best_digit = digit
    return best_digit if best_score <= 2 else None
