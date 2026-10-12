# kiln

FastAPI dashboard for kiln monitoring:

- ambient temperature from DHT11
- humidity from DHT11
- kiln temperature parsed from a camera frame

Readings are stored in `data/readings.sqlite3`. If `data/readings.csv` exists from an
older run, it is imported into SQLite once on startup.

The browser refreshes chart data only while the tab is active.

## Remote PHP dashboard

The root `receive.php` endpoint accepts a JSON POST and saves it to SQLite at
`data/readings.sqlite3` on the PHP server. `index.php` displays the most recent
measurement and the last 100 readings, refreshing every 10 seconds. The PHP
server needs PHP's SQLite3 extension and write access to the `data/` directory.
Set a long random token in the PHP server environment as `KILN_API_TOKEN`;
requests without the matching `Authorization: Bearer <token>` are rejected.

To send readings from this collector, set these environment variables for the
Python service (for example, add them to `scripts/kiln.service`):

```ini
Environment=KILN_REMOTE_URL=https://your-server.example/receive.php
Environment=KILN_REMOTE_TOKEN=<same-random-token-as-KILN_API_TOKEN>
Environment=KILN_REMOTE_INTERVAL=10
```

The JSON record contains `timestamp` (UTC ISO 8601), `ambient_temperature`
(°C), `humidity` (%), `kiln_temperature` (°C), and `source` (`camera` or
`video`). The three measurements may be `null` if unavailable. For migration to
MySQL, these map naturally to `timestamp` (DATETIME/TIMESTAMP), three nullable
`DOUBLE` columns, and `source` (VARCHAR); keep a unique key on `timestamp`.

When you are ready to provide MySQL connection details, send the hostname, port,
database name, username, password (preferably a dedicated restricted user),
whether TLS is required, and the PHP server's base URL. Do not put credentials
in chat if you can instead configure them as environment variables on the
server.

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

Optional filters:

```bash
KILN_MAX_STEP=15 KILN_CONFIRMATION_TOLERANCE=3 .venv/bin/python main.py
```
