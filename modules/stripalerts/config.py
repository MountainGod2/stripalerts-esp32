"""Configuration management."""

import json

from micropython import const

from .utils import log_error, log_warning

CONFIG_FILE = const("/config.json")

# Default configuration
DEFAULTS = {
    "led_pin": 48,
    "num_pixels": 60,
    "led_timing": 1,
    "led_pattern": "rainbow",
    "rainbow_step": 0.2,
    "rainbow_delay": 0.01,
    "api_url": "https://events.testbed.cb.dev/events/mountaingod2/test/",
    "wifi_ssid": "",
    "wifi_password": "",
}


class Config:
    """Simple configuration manager."""

    def __init__(self) -> None:
        self._data = DEFAULTS.copy()
        self.load()

    def load(self) -> None:
        """Load configuration from disk."""
        try:
            with open(CONFIG_FILE) as f:
                self._data.update(json.load(f))
        except (OSError, ValueError) as e:
            log_warning(f"Using default config ({e})")

    def save(self) -> None:
        """Save configuration to disk."""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._data, f)
        except OSError as e:
            log_error(f"Save failed: {e}")

    def __getitem__(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)


# Singleton instance
settings = Config()
