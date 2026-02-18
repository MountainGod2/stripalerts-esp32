"""Constants for StripAlerts.

Note: Hardware configuration values have been moved to config.py.
This file is kept for any true constants that should never change.
"""

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    RGB = tuple[int, int, int]
else:
    RGB = tuple

from micropython import const

APP_NAME = "StripAlerts"

MAX_PIXELS = const(300)
MIN_PIN = const(0)
MAX_PIN = const(48)

WIFI_CONNECT_TIMEOUT = const(10)
HTTP_REQUEST_TIMEOUT = const(5)

# Trigger Tokens
TRIGGER_TOKEN_AMOUNT = const(35)

# LED Brightness (0.0 - 1.0)
LED_BRIGHTNESS = 0.5

# Event queue size
MAX_EVENT_QUEUE_SIZE = const(50)

# Effect durations (in seconds)
TIP_PULSE_DURATION = 2.0
COLOR_HOLD_DURATION = const(600)  # 10 minutes

# BLE Protocol constants
BLE_MAX_PAYLOAD_SIZE = const(240)  # Default MTU is 23 bytes with ~20 bytes payload
BLE_MAX_NETWORKS_LIST = const(5)


# Color mapping for tips
COLOR_MAP: "dict[str, RGB]" = {
    "red": (255, 0, 0),
    "orange": (255, 165, 0),
    "yellow": (255, 255, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "indigo": (75, 0, 130),
    "violet": (238, 130, 238),
}
