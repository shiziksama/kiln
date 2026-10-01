class DHTSensor:
    def __init__(self) -> None:
        self._sensor = None
        try:
            import adafruit_dht
            import board

            self._sensor = adafruit_dht.DHT11(board.D4)
        except Exception:
            self._sensor = None

    def read(self) -> tuple[float | None, float | None]:
        if self._sensor is None:
            return None, None
        try:
            return self._sensor.temperature, self._sensor.humidity
        except RuntimeError:
            return None, None
