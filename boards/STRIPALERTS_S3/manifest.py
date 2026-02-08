"""Manifest for StripAlerts MCU."""

# Include the base ESP32 manifest
include("$(PORT_DIR)/boards/manifest.py")
require("aioble")
require("aiohttp")

# Freeze StripAlerts package
freeze(
    "$(MPY_DIR)/../../lib",
    (
        "stripalerts/__init__.py",
        "stripalerts/api.py",
        "stripalerts/app.py",
        "stripalerts/ble.py",
        "stripalerts/config.py",
        "stripalerts/constants.py",
        "stripalerts/events.py",
        "stripalerts/led.py",
        "stripalerts/utils.py",
        "stripalerts/version.py",
        "stripalerts/wifi.py",
    ),
    opt=3,
)
