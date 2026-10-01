import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


@dataclass(slots=True)
class Reading:
    timestamp: str
    ambient_temperature: float | None
    humidity: float | None
    kiln_temperature: float | None
    source: str


class ReadingStore:
    def __init__(self, path: Path, max_readings: int, csv_import_path: Path | None = None) -> None:
        self.path = path
        self.max_readings = max_readings
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connect()
        self._create_schema()
        if csv_import_path is not None:
            self._import_csv_once(csv_import_path)

    def add(
        self,
        *,
        ambient_temperature: float | None,
        humidity: float | None,
        kiln_temperature: float | None,
        source: str,
    ) -> Reading:
        reading = Reading(
            timestamp=datetime.now(timezone.utc).isoformat(),
            ambient_temperature=ambient_temperature,
            humidity=humidity,
            kiln_temperature=kiln_temperature,
            source=source,
        )
        with self._lock:
            self._insert(reading)
        return reading

    def latest(self) -> Reading | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT timestamp, ambient_temperature, humidity, kiln_temperature, source
                FROM readings
                ORDER BY timestamp DESC
                LIMIT 1
                """
            ).fetchone()
        return _row_to_reading(row) if row else None

    def all(self) -> list[Reading]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT timestamp, ambient_temperature, humidity, kiln_temperature, source
                FROM readings
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (self.max_readings,),
            ).fetchall()
        return [_row_to_reading(row) for row in reversed(rows)]

    def minutely(self, limit: int | None = None) -> list[Reading]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT
                    substr(timestamp, 1, 16) || ':00+00:00' AS timestamp,
                    AVG(ambient_temperature) AS ambient_temperature,
                    AVG(humidity) AS humidity,
                    AVG(kiln_temperature) AS kiln_temperature,
                    'minute' AS source
                FROM readings
                GROUP BY substr(timestamp, 1, 16)
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit or self.max_readings,),
            ).fetchall()
        return [_row_to_reading(row) for row in reversed(rows)]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _connect(self) -> None:
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.row_factory = sqlite3.Row

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL UNIQUE,
                    ambient_temperature REAL,
                    humidity REAL,
                    kiln_temperature REAL,
                    source TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp)"
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def _insert(self, reading: Reading) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO readings (
                    timestamp,
                    ambient_temperature,
                    humidity,
                    kiln_temperature,
                    source
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    reading.timestamp,
                    reading.ambient_temperature,
                    reading.humidity,
                    reading.kiln_temperature,
                    reading.source,
                ),
            )

    def _import_csv_once(self, csv_path: Path) -> None:
        if not csv_path.exists():
            return
        imported_count = self._connection.execute(
            "SELECT value FROM metadata WHERE key = 'csv_imported'"
        ).fetchone()
        if imported_count is not None:
            return

        with csv_path.open("r", newline="", encoding="utf-8") as file:
            rows = csv.DictReader(file)
            with self._connection:
                for row in rows:
                    self._connection.execute(
                        """
                        INSERT OR IGNORE INTO readings (
                            timestamp,
                            ambient_temperature,
                            humidity,
                            kiln_temperature,
                            source
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            row["timestamp"],
                            _float_or_none(row["ambient_temperature"]),
                            _float_or_none(row["humidity"]),
                            _float_or_none(row["kiln_temperature"]),
                            row.get("source") or "unknown",
                        ),
                    )
                self._connection.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES ('csv_imported', ?)",
                    (datetime.now(timezone.utc).isoformat(),),
                )


def _row_to_reading(row: sqlite3.Row) -> Reading:
    return Reading(
        timestamp=row["timestamp"],
        ambient_temperature=row["ambient_temperature"],
        humidity=row["humidity"],
        kiln_temperature=row["kiln_temperature"],
        source=row["source"],
    )


def _float_or_none(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
