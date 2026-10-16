#!/usr/bin/env python3
"""Make a three-panel video: source, Tesseract input, and Tesseract result."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from collections import deque
from pathlib import Path

import cv2
import numpy as np


WINDOW_SIZE = 1
MASK_THRESHOLD = 220
OCR_EVERY_N_FRAMES = 30


def find_display(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    joined = cv2.dilate(mask, np.ones((19, 31), np.uint8), iterations=1)
    contours, _ = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [
        cv2.boundingRect(contour)
        for contour in contours
        if (box := cv2.boundingRect(contour))[2] >= 80
        and box[3] >= 45
        and box[2] / box[3] >= 1.4
    ]
    return max(boxes, key=lambda box: box[2] * box[3]) if boxes else None


def make_ocr_input(frame: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    """Return the original crop selected by the binary display locator."""
    x, y, width, height = box
    padding = 8
    crop = frame[
        max(0, y - padding) : min(frame.shape[0], y + height + padding),
        max(0, x - padding) : min(frame.shape[1], x + width + padding),
    ]
    return crop


def read_with_tesseract(image: np.ndarray) -> str | None:
    with tempfile.NamedTemporaryFile(suffix=".png") as source:
        cv2.imwrite(source.name, image)
        result = subprocess.run(
            [
                "tesseract",
                source.name,
                "stdout",
                "--psm",
                "7",
                "-c",
                "tessedit_char_whitelist=0123456789",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    value = "".join(character for character in result.stdout if character.isdigit())
    return value or None


def label(panel: np.ndarray, text: str) -> np.ndarray:
    result = panel.copy()
    cv2.rectangle(result, (12, 12), (panel.shape[1] - 12, 65), (0, 0, 0), -1)
    cv2.putText(result, text, (25, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    return result


def input_panel(ocr_input: np.ndarray, width: int, height: int) -> np.ndarray:
    panel = np.zeros((height, width, 3), dtype=np.uint8)
    scale = min((width - 80) / ocr_input.shape[1], (height - 120) / ocr_input.shape[0])
    preview = cv2.resize(ocr_input, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    top = (height - preview.shape[0]) // 2 + 30
    left = (width - preview.shape[1]) // 2
    if preview.ndim == 2:
        preview = cv2.cvtColor(preview, cv2.COLOR_GRAY2BGR)
    panel[top : top + preview.shape[0], left : left + preview.shape[1]] = preview
    return label(panel, "2. exact Tesseract input (raw crop)")


def result_panel(value: str | None, width: int, height: int) -> np.ndarray:
    panel = np.zeros((height, width, 3), dtype=np.uint8)
    text = value or "?"
    font_scale = 5
    size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 8)
    cv2.putText(
        panel,
        text,
        ((width - size[0]) // 2, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (255, 255, 255),
        8,
    )
    return label(panel, "3. Tesseract result")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if shutil.which("tesseract") is None:
        raise SystemExit("Install Tesseract first: sudo apt install tesseract-ocr")

    output = args.output or args.input.with_name(f"{args.input.stem}.tesseract-debug.mp4")
    capture = cv2.VideoCapture(str(args.input))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    panel_width = width // 2
    panel_height = height // 2
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    writer = cv2.VideoWriter(
        str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (panel_width * 3, panel_height)
    )
    red_frames: deque[np.ndarray] = deque(maxlen=WINDOW_SIZE)
    value: str | None = None
    frame_index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            red_frames.append(frame[:, :, 2])
            integrated_red = np.maximum.reduce(red_frames)
            mask = cv2.threshold(integrated_red, MASK_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
            box = find_display(mask) if len(red_frames) == WINDOW_SIZE else None
            ocr_input = make_ocr_input(frame, box) if box else np.zeros((1, 1), np.uint8)
            if box and frame_index % OCR_EVERY_N_FRAMES == OCR_EVERY_N_FRAMES - 1:
                value = read_with_tesseract(ocr_input)

            source = label(cv2.resize(frame, (panel_width, panel_height)), "1. original video")
            if box:
                x, y, box_width, box_height = box
                cv2.rectangle(
                    source,
                    (x // 2, y // 2),
                    ((x + box_width) // 2, (y + box_height) // 2),
                    (0, 255, 0),
                    2,
                )
            writer.write(
                np.hstack(
                    (
                        source,
                        input_panel(ocr_input, panel_width, panel_height),
                        result_panel(value, panel_width, panel_height),
                    )
                )
            )
            frame_index += 1
    finally:
        capture.release()
        writer.release()
    print(f"Wrote {frame_index} frames to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
