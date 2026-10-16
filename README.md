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
120 readings plus minute averages.

## Remote PHP dashboard

The root `receive.php` endpoint accepts a JSON POST and saves it to SQLite at
`data/readings.sqlite3` on the PHP server. `index.php` renders the two
charts as the old dashboard: recent readings and per-minute averages, with
independent toggles for each measurement. It reads chart data from the same PHP
file and refreshes every 10 seconds. The PHP server needs PHP's SQLite3
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
