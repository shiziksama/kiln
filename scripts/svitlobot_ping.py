#!/usr/bin/env python3
"""Keep a SvitloBot channel alive with periodic ping requests."""

import logging
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PING_URL = "https://api.svitlobot.in.ua/channelPing"
INTERVAL_SECONDS = 70
REQUEST_TIMEOUT_SECONDS = 15


def ping(channel_key: str) -> None:
    url = f"{PING_URL}?{urlencode({'channel_key': channel_key})}"
    request = Request(url, headers={"User-Agent": "curl/8.0.0"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response.read()
            logging.info("SvitloBot ping returned HTTP %s", response.status)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        logging.warning("SvitloBot ping failed: %s", error)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    channel_key = os.environ.get("SVITLOBOT_CHANNEL_KEY", "").strip()
    if not channel_key:
        raise SystemExit("SVITLOBOT_CHANNEL_KEY must be configured")

    while True:
        ping(channel_key)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
