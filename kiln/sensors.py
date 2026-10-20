import logging
import time


logger = logging.getLogger(__name__)


class DHTSensor:
    def __init__(self) -> None:
        self._sensor = None
        self._last_warning: float | None = None
        try:
            import adafruit_dht
            import board

            self._sensor = adafruit_dht.DHT11(board.D4)
        except Exception:
            logger.exception("DHT11 initialization failed on GPIO4 (physical pin 7)")

    def read(self) -> tuple[float | None, float | None]:
        if self._sensor is None:
            return None, None
        try:
            reading = self._sensor.temperature, self._sensor.humidity
        except RuntimeError as error:
            now = time.monotonic()
            if self._last_warning is None or now - self._last_warning >= 60:
                logger.warning("DHT11 read failed on GPIO4: %s", error)
                self._last_warning = now
            return None, None
        if self._last_warning is not None:
            logger.warning("DHT11 readings recovered on GPIO4")
            self._last_warning = None
        return reading
