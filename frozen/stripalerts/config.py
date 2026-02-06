"""Configuration management for StripAlerts."""

import json
import pathlib

from micropython import const

CONFIG_FILE = const("/config.json")

_DEFAULT_CONFIG = (
    ("led_pin", 48),
    ("num_pixels", 1),
    ("led_timing", 1),  # 1 for 800kHz NeoPixel (default), 0 for 400kHz
    ("led_pattern", "rainbow"),
    ("rainbow_step", 1),
    ("rainbow_delay", 0.1),
    ("api_url", "https://events.testbed.cb.dev/events/mountaingod2/test/"),
    ("wifi_ssid", None),
    ("wifi_password", None),
    ("ble_enabled", False),
    ("ble_name", "StripAlerts"),
)


class Config:
    """Configuration manager with persistence."""

    def __init__(self) -> None:
        """Initialize configuration."""
        self._config = {}
        for key, value in _DEFAULT_CONFIG:
            self._config[key] = value
        self._loaded = False
        self.load()

    def load(self) -> bool:
        """Load configuration from JSON file.

        Returns:
            True if loaded successfully, False otherwise

        """
        try:
            with pathlib.Path(CONFIG_FILE).open() as f:
                loaded_config = json.load(f)
                self._config.update(loaded_config)
                self._loaded = True
                return True
        except OSError as e:
            from .utils import log_warning

            log_warning(f"Config file not found, using defaults: {e}")
            return False
        except ValueError as e:
            from .utils import log_error

            log_error(f"Invalid JSON in config file: {e}")
            return False

    def save(self) -> bool:
        """Save configuration to JSON file.

        Returns:
            True if saved successfully, False otherwise

        """
        try:
            with pathlib.Path(CONFIG_FILE).open("w") as f:
                json.dump(self._config, f)
            return True
        except OSError as e:
            from .utils import log_error

            log_error(f"Failed to save config: {e}")
            return False

    def get(self, key: str, default=None):
        """Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default

        """
        return self._config.get(key, default)

    def set(self, key: str, value) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set

        """
        self._config[key] = value

    def update(self, values: dict) -> None:
        """Update multiple configuration values.

        Args:
            values: Dictionary of key-value pairs to update

        """
        self._config.update(values)

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self._config = dict(_DEFAULT_CONFIG)

    def as_dict(self) -> dict:
        """Get configuration as dictionary.

        Returns:
            Configuration dictionary

        """
        return self._config.copy()


# Singleton instance
settings = Config()
