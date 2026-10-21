# kiln

The Raspberry Pi runs a Python collector. It reads sensors and sends readings
to the PHP receiver; Python does not store readings in a local database. The
PHP site stores them in its server-side SQLite database and renders the
dashboard and charts; FastAPI is not used.

- ambient temperature from DHT11
- humidity from DHT11
- kiln temperature parsed from a camera frame when available

If no camera is connected, collection continues using the DHT11 sensor. The
kiln temperature is sent as `null` and the reading source is `sensor-only`.
If `KILN_REMOTE_URL` is unset, readings are collected but not retained.

The PHP dashboard refreshes its charts every 10 seconds and shows the latest
120 readings plus minute averages for the last 24 hours (1440 minute slots).
Missing values break chart lines. Hover over either chart to inspect values.
Zoom the minute chart with the mouse wheel or +/− buttons, drag to pan, and
use “Усі 24 години” to reset. Zoom ranges from 10 minutes to the full day
and stays selected across data refreshes.
The header shows elapsed time since the latest reading and the last successful
data fetch; both timers update every second.

## Remote PHP dashboard

The root `receive.php` endpoint accepts a JSON POST and saves it to SQLite at
`data/readings.sqlite3` on the PHP server. `index.php` renders the two
charts as the old dashboard: recent readings and per-minute averages, with
independent toggles for each measurement. `index.php` serves the dashboard markup; the browser fetches JSON from
`data.php` immediately and every 10 seconds while the page is visible.
`data.php` reads SQLite and returns `readings`, `minutes`, and `latest`. The PHP server needs PHP's SQLite3
extension and write access to the `data/` directory. The receiver accepts POST
requests without authentication.

To send readings from this collector, set these environment variables for the
Python service (for example, add them to `scripts/kiln.service`):

```ini
Environment=KILN_REMOTE_URL=https://your-server.example/receive.php
Environment=KILN_REMOTE_INTERVAL=10
```

The JSON record contains `timestamp` (UTC ISO 8601), `ambient_temperature`
(°C), `humidity` (%), `kiln_temperature` (°C), and `source` (`camera`, `video`,
or `sensor-only`). The three measurements may be `null` if unavailable. For migration to
MySQL, these map naturally to `timestamp` (DATETIME/TIMESTAMP), three nullable
`DOUBLE` columns, and `source` (VARCHAR); keep a unique key on `timestamp`.

When you are ready to provide MySQL connection details, send the hostname, port,
database name, username, password, whether TLS is required, and the PHP server's
base URL.

## Run the collector

```bash
.venv/bin/python main.py
```

## Systemd

The collector service is `kiln.service`.

```bash
sudo systemctl status kiln.service
sudo systemctl restart kiln.service
```

Logs:

```bash
journalctl -u kiln.service -f
```

`kiln.service` starts `kiln-svitlobot-ping.service` with it. Add the SvitloBot
channel key to the project `.env` file:

```bash
printf 'SVITLOBOT_CHANNEL_KEY=%s\n' '<YOUR_CHANNEL_KEY>' >> .env
sudo systemctl daemon-reload
sudo systemctl restart kiln.service
```

The service then pings the channel every 70 seconds. View its logs with:

```bash
journalctl -u kiln-svitlobot-ping.service -f
```

## Sources

Use the sample video:

```bash
KILN_SOURCE=video .venv/bin/python main.py
```

Use the camera:

```bash
KILN_SOURCE=camera KILN_CAMERA_INDEX=/dev/v4l/by-id/usb-Jieli_Technology_USB_Composite_Device-video-index0 .venv/bin/python main.py
```

USB capture defaults to V4L2 + MJPG 1280x720 at 30 FPS. Override if needed:

```bash
KILN_CAMERA_BACKEND=v4l2 KILN_CAMERA_FOURCC=MJPG KILN_CAMERA_WIDTH=1280 KILN_CAMERA_HEIGHT=720 KILN_CAMERA_FPS=30 KILN_CAMERA_WARMUP_SECONDS=3 .venv/bin/python main.py
```

## Display Calibration

The red display panel is located automatically by default, so small camera
movements do not invalidate the crop. Digits are read by Tesseract. To disable
automatic location and use manual coordinates:

```bash
KILN_AUTO_DISPLAY=0 KILN_DISPLAY_ROI=510,225,110,65 KILN_DIGITS_ROI=23,17,66,32 .venv/bin/python main.py
```

Format is `x,y,width,height`. The digits ROI is relative to the display crop.
These defaults were calibrated for the current camera position at 1280x720;
recalibrate for other positions, resolutions, or the archived sample video.

The dashboard shows the latest display crop so the ROI can be checked visually.


## Camera and Tesseract experiments

Recognition uses Tesseract only, with the bundled display font model, a digit
whitelist, and PSM 7, 13 and 8. Complete results are compared across modes.
Model provenance and license are in `models/tessdata/README.md`. The
input is enlarged 4x, thresholded with Otsu, and inverted to dark digits on a
white background with padding. `KILN_OCR_CHANNEL=green` is the default;
`red`, `blue`, and `gray` are also supported. On the current bright red display,
the red channel saturates the background; green preserves more digit contrast.
The collector requires a strict majority over a burst of 12 frames. Each result
must contain all three digits, including leading zeros (`KILN_OCR_DIGITS=3`).
The supported temperature range is 0..999°C. A plausible result from one frame
is not proof of accuracy; validate at other displayed temperatures.

Capture eight frames and save each full frame, display crop, processed channel
images, raw Tesseract text, and `report.json` locally (no sensor reads or uploads):

```bash
.venv/bin/python scripts/camera_probe.py --output data/camera-experiment/new
```

The probe accepts `--camera 1` or a stable `/dev/v4l/by-id/...-video-index0`
path, plus `--width`, `--height`, `--samples`, and `--warmup`. It restores the
previous capture format on exit. Run only when the camera is free. To compare
saved frames again without opening the camera:

```bash
.venv/bin/python scripts/camera_probe.py --input data/camera-experiment --output data/camera-experiment/analysis
```

The probe scales the 720p calibration to the captured frame size, assuming the
same camera view. The collector uses ROI coordinates exactly as configured.
Camera experiment files are ignored by Git under `data/`. Changes to the unit
in `scripts/kiln.service` must be installed and systemd reloaded before they
affect the running service.

The installed service can use the camera settings drop-in without replacing its
other settings:

```bash
sudo install -m 644 scripts/camera.conf /etc/systemd/system/kiln.service.d/camera.conf
sudo systemctl daemon-reload
sudo systemctl restart kiln.service
```

Successful receiver acknowledgments are logged as `Reading uploaded` with the
actual measurements. Run the OCR checks (including all ten synthetic digit
shapes and real 025/026 crops at shifted positions):

```bash
.venv/bin/python -m unittest discover -s tests -v
```
