"""Manifest for StripAlerts MCU."""

# Include the base ESP32 manifest
include("$(PORT_DIR)/boards/manifest.py")
require("aioble")
require("aiohttp")

# Freeze StripAlerts package
freeze(
    "$(MPY_DIR)/../../modules/stripalerts",
    (
        "__init__.py",
        "api.py",
        "app.py",
        "ble.py",
        "config.py",
        "constants.py",
        "events.py",
        "led.py",
        "utils.py",
        "version.py",
        "wifi.py",
    ),
    opt=3,
)
