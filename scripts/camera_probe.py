"""Save camera bursts and compare Tesseract input channels without uploading readings."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kiln.settings import parse_roi
from kiln.vision import (
    DEFAULT_DISPLAY_ROI, DEFAULT_DIGITS_ROI, _parse_number,
    _prepare_for_ocr, _run_tesseract, extract_display, read_kiln_temperature,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Analyze saved frame-*.jpg files instead of opening a camera')
    parser.add_argument('--output', type=Path, default=Path('data/camera-experiment'))
    parser.add_argument('--camera', default=os.getenv('KILN_CAMERA_INDEX', '/dev/v4l/by-id/usb-Jieli_Technology_USB_Composite_Device-video-index0'))
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=720)
    parser.add_argument('--samples', type=int, default=8)
    parser.add_argument('--warmup', type=float, default=3)
    args = parser.parse_args()
    if args.samples < 1 or args.width < 1 or args.height < 1 or args.warmup < 0:
        parser.error('samples and dimensions must be positive; warmup must be nonnegative')
    args.output.mkdir(parents=True, exist_ok=True)
    display_roi = parse_roi('KILN_DISPLAY_ROI', DEFAULT_DISPLAY_ROI)
    digits_roi = parse_roi('KILN_DIGITS_ROI', DEFAULT_DIGITS_ROI)
    frames = []
    if args.input:
        for path in sorted(args.input.glob('frame-*.jpg')):
            frame = cv2.imread(str(path))
            if frame is None:
                raise RuntimeError(f'Cannot read {path}')
            frames.append((path.stem, frame))
    else:
        device = int(args.camera) if args.camera.isdecimal() else args.camera
        capture = cv2.VideoCapture(device, cv2.CAP_V4L2)
        original_width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        original_height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        original_fourcc = capture.get(cv2.CAP_PROP_FOURCC)
        original_fps = capture.get(cv2.CAP_PROP_FPS)
        try:
            if not capture.isOpened():
                raise RuntimeError(f'Cannot open camera {device}')
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            deadline = time.monotonic() + args.warmup
            while time.monotonic() < deadline:
                ok, _ = capture.read()
                if not ok:
                    raise RuntimeError('Camera read failed during warmup')
            for i in range(args.samples):
                ok, frame = capture.read()
                if not ok or frame is None:
                    raise RuntimeError(f'Camera read failed at sample {i}')
                name = f'frame-{frame.shape[1]}x{frame.shape[0]}-{time.time_ns()}-{i:02}'
                if not cv2.imwrite(str(args.output / f'{name}.jpg'), frame):
                    raise RuntimeError('Cannot save frame')
                frames.append((name, frame))
        finally:
            if capture.isOpened():
                capture.set(cv2.CAP_PROP_FOURCC, original_fourcc)
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, original_width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, original_height)
                capture.set(cv2.CAP_PROP_FPS, original_fps)
            capture.release()
    if not frames:
        raise RuntimeError('No frames found')
    results = []
    for name, frame in frames:
        # Calibration coordinates refer to a 1280x720 frame of the same 16:9 view.
        sx, sy = frame.shape[1] / 1280, frame.shape[0] / 720
        def scaled(roi):
            return tuple(round(v * (sx if i % 2 == 0 else sy)) for i, v in enumerate(roi))
        display, digits = extract_display(frame, scaled(display_roi), scaled(digits_roi))
        if display.size == 0 or digits.size == 0:
            raise RuntimeError(f'ROI outside frame {name}')
        cv2.imwrite(str(args.output / f'{name}-display.png'), display)
        row = {'frame': name, 'width': frame.shape[1], 'height': frame.shape[0], 'ocr': {}}
        for channel in ('red', 'green', 'blue', 'gray'):
            mask = _prepare_for_ocr(digits, channel)
            path = args.output / f'{name}-{channel}.png'
            cv2.imwrite(str(path), mask)
            row['ocr'][channel] = _run_tesseract(mask)
        row['temperature'] = read_kiln_temperature(frame, display_roi=scaled(display_roi), digits_roi=scaled(digits_roi))
        results.append(row)
        print(name, row['ocr'], flush=True)
    summary = {
        channel: dict(Counter(str(_parse_number(row['ocr'][channel])) for row in results))
        for channel in ('red', 'green', 'blue', 'gray')
    }
    report = {'display_roi_720p': display_roi, 'digits_roi_720p': digits_roi,
              'results': results, 'value_counts': summary}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
