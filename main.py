import time
from datetime import datetime
from pathlib import Path

import board
import adafruit_dht
import cv2
import pytesseract

dht = adafruit_dht.DHT11(board.D4)

photos_dir = Path("photos")
photos_dir.mkdir(exist_ok=True)

camera = cv2.VideoCapture(0)  # 0 = перша USB камера

if not camera.isOpened():
    raise RuntimeError("Camera not found")

while True:
    try:
        temperature = dht.temperature
        humidity = dht.humidity

        print(f"Temperature: {temperature}°C")
        print(f"Humidity: {humidity}%")

        ok, frame = camera.read()
        

        if ok:
            x = 300
            y = 250
            w = 100
            h = 50

            roi = frame[y:y+h, x:x+w]


            display = cv2.resize(
                roi,
                None,
                fx=5,
                fy=5,
                interpolation=cv2.INTER_CUBIC
            )
            cv2.imwrite("photos/debug1.png", display)


            gray = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)
            cv2.imwrite("photos/debug2.png", gray)

            gray = cv2.convertScaleAbs(
                gray,
                alpha=2.0,
                beta=20
            )
            cv2.imwrite("photos/debug3.png", gray)

            _, binary = cv2.threshold(
                gray,
                120,
                255,
                cv2.THRESH_BINARY
            )
            cv2.imwrite("photos/debug4.png", binary)

            









            config = (
                "--oem 3 "
                "--psm 7 "
                "-c tessedit_char_whitelist=0123456789."
            )

            text = pytesseract.image_to_string(
                gray,
                config=config
            )

            print("text" + text)

            cv2.imwrite("photos/crop.jpg", roi)

            filename = "screenshot.jpg"
            path = photos_dir / filename
            cv2.imwrite(str(path), frame)
            print(f"Saved photo: {path}")
        else:
            print("Failed to capture image")

    except RuntimeError as e:
        print(e)

    time.sleep(3)