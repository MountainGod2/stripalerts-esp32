"""Constants for StripAlerts.

Note: Hardware configuration values have been moved to config.py.
This file is kept for any true constants that should never change.
"""

from micropython import const

APP_NAME = "StripAlerts"

MAX_PIXELS = const(300)
MIN_PIN = const(0)
MAX_PIN = const(48)

WIFI_CONNECT_TIMEOUT = const(10)
HTTP_REQUEST_TIMEOUT = const(5)

# Trigger Tokens
TRIGGER_TOKEN_AMOUNT = const(35)

# Event queue size
MAX_EVENT_QUEUE_SIZE = const(50)


# Color mapping for tips
COLOR_MAP = {
    "red": (255, 0, 0),
    "orange": (255, 165, 0),
    "yellow": (255, 255, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "indigo": (75, 0, 130),
    "violet": (238, 130, 238),
}
