from pathlib import Path
import time

import cv2


WARMUP_SECONDS = 3.0
SAMPLES_AFTER_WARMUP = 5


def main() -> None:
    Path("static").mkdir(exist_ok=True)
    for index in (0, 1):
        capture = cv2.VideoCapture(index, cv2.CAP_V4L2)
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        capture.set(cv2.CAP_PROP_FPS, 30)
        print(f"index {index} opened {capture.isOpened()}")
        deadline = time.monotonic() + WARMUP_SECONDS
        while time.monotonic() < deadline:
            capture.read()
        for sample in range(SAMPLES_AFTER_WARMUP):
            ok, frame = capture.read()
            print(f"index {index} sample {sample} read {ok} {None if frame is None else frame.shape}")
            suffix = "" if sample == 0 else f"-{sample}"
            saved = cv2.imwrite(f"static/camera-test-{index}{suffix}.jpg", frame) if ok else False
            print(f"index {index} sample {sample} saved {saved}")
        capture.release()


if __name__ == "__main__":
    main()
