"""Manifest for StripAlerts MCU."""

# Include the base ESP32 manifest
include("$(PORT_DIR)/boards/manifest.py")
require("aioble")
require("aiohttp")

# Freeze StripAlerts package
freeze("$(MPY_DIR)/../../modules/stripalerts", opt=3)
