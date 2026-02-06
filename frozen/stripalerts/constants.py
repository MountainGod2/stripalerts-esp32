"""Constants for StripAlerts.

Note: Hardware configuration values have been moved to config.py.
This file is kept for any true constants that should never change.
"""

from micropython import const

# Application metadata
APP_NAME = "StripAlerts"

# Hardware limits
MAX_PIXELS = const(300)
MIN_PIN = const(0)
MAX_PIN = const(48)

# Network timeouts (seconds)
WIFI_CONNECT_TIMEOUT = const(10)
HTTP_REQUEST_TIMEOUT = const(5)

# Event queue size
MAX_EVENT_QUEUE_SIZE = const(50)
