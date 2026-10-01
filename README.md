# kiln

FastAPI dashboard for kiln monitoring:

- ambient temperature from DHT11
- humidity from DHT11
- kiln temperature parsed from a camera frame

Readings are stored in `data/readings.sqlite3`. If `data/readings.csv` exists from an
older run, it is imported into SQLite once on startup.

The browser refreshes chart data only while the tab is active.

## Run

```bash
.venv/bin/python main.py
```

Open `http://<raspberry-pi-ip>:8000`.

For local testing when `8000` is busy:

```bash
HOST=127.0.0.1 PORT=8010 .venv/bin/python main.py
```

## Systemd

The local dashboard service is `kiln.service`.

```bash
sudo systemctl status kiln.service
sudo systemctl restart kiln.service
```

The optional public ngrok tunnel service is `kiln-ngrok.service`. It starts only
after an ngrok authtoken is configured:

```bash
ngrok config add-authtoken "<YOUR_AUTHTOKEN>"
sudo systemctl enable --now kiln-ngrok.service
```

Logs:

```bash
journalctl -u kiln.service -f
journalctl -u kiln-ngrok.service -f
```

## Sources

Use the sample video:

```bash
KILN_SOURCE=video .venv/bin/python main.py
```

Use the camera:

```bash
KILN_SOURCE=camera KILN_CAMERA_INDEX=0 .venv/bin/python main.py
```

USB capture defaults to V4L2 + MJPG 1280x720 at 30 FPS. Override if needed:

```bash
KILN_CAMERA_BACKEND=v4l2 KILN_CAMERA_FOURCC=MJPG KILN_CAMERA_WIDTH=1280 KILN_CAMERA_HEIGHT=720 KILN_CAMERA_FPS=30 KILN_CAMERA_WARMUP_SECONDS=3 .venv/bin/python main.py
```

## Display Calibration

The display crop is configurable without changing code:

```bash
KILN_DISPLAY_ROI=220,560,315,175 KILN_DIGITS_ROI=90,30,210,110 .venv/bin/python main.py
```

Format is `x,y,width,height`.

The dashboard shows the latest display crop so the ROI can be checked visually.

Optional filters:

```bash
KILN_MAX_STEP=15 KILN_CONFIRMATION_TOLERANCE=3 .venv/bin/python main.py
```
