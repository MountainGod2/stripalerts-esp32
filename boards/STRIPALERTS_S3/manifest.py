"""Manifest for StripAlerts ESP32S3 board."""

# Include the base ESP32 manifest
include("$(PORT_DIR)/boards/manifest.py")

# Freeze StripAlerts package
freeze(
	"$(MPY_DIR)/../../frozen",
	(
		"stripalerts/__init__.py",
		"stripalerts/app.py",
		"stripalerts/ble.py",
		"stripalerts/config.py",
		"stripalerts/constants.py",
		"stripalerts/events.py",
		"stripalerts/led.py",
		"stripalerts/ota.py",
		"stripalerts/utils.py",
		"stripalerts/version.py",
		"stripalerts/wifi.py",
	),
	opt=3,
)
