import time
import board
import adafruit_dht

dht = adafruit_dht.DHT11(board.D4)

while True:
    try:
        print(f"Temperature: {dht.temperature}°C")
        print(f"Humidity: {dht.humidity}%")
    except RuntimeError as e:
        print(e)

    time.sleep(2)