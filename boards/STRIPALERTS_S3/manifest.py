"""Manifest for StripAlerts ESP32S3 board."""

# Include the base ESP32 manifest
include("$(PORT_DIR)/boards/manifest.py")

# Freeze StripAlerts package
freeze("$(MPY_DIR)/../../frozen", "stripalerts", opt=3)
