"""Configuration management."""

import json
import os

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    from typing import Any

from micropython import const

from .constants import MAX_API_URL_LEN, MAX_WIFI_PASSWORD_LEN, MAX_WIFI_SSID_LEN
from .utils import log_error, log_warning

CONFIG_FILE = const("/config.json")

DEFAULTS = {
    "led_pin": 16,
    "num_pixels": 60,
    "led_timing": 1,
    "rainbow_step": 0.05,
    "rainbow_delay": 0.01,
    "api_url": "https://events.testbed.cb.dev/events/mountaingod2/test/",
    "wifi_ssid": "",
    "wifi_password": "",
}

try:
    machine = os.uname().machine
    board_defaults: dict = {
        "led_pin": 48 if "ESP32S3" in machine else 16,
    }
    DEFAULTS.update(board_defaults)
except Exception as e:
    log_warning(f"Failed to get board defaults: {e}")


class Config:
    """Simple configuration manager."""

    @staticmethod
    def _sanitize_value(key: str, value: "Any") -> "Any":
        """Normalize user-provided config values to safe runtime types."""
        if key in {"wifi_ssid", "wifi_password", "api_url"}:
            if not isinstance(value, str):
                return ""
            value = value.strip()
            if key == "wifi_ssid":
                return value[:MAX_WIFI_SSID_LEN]
            if key == "wifi_password":
                return value[:MAX_WIFI_PASSWORD_LEN]
            if key == "api_url":
                if not value.startswith(("http://", "https://")):
                    return ""
                return value[:MAX_API_URL_LEN]
            return value

        if key in {"led_pin", "num_pixels"}:
            try:
                return int(value)
            except (TypeError, ValueError):
                return DEFAULTS.get(key)

        if key in {"led_timing", "rainbow_step", "rainbow_delay"}:
            try:
                return float(value)
            except (TypeError, ValueError):
                return DEFAULTS.get(key)

        return value

    def __init__(self) -> None:
        """Initialize configuration manager and load settings."""
        self._data: "dict[str, Any]" = DEFAULTS.copy()
        self.load()

    def load(self) -> None:
        """Load configuration from disk."""
        try:
            with open(CONFIG_FILE) as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for key, value in loaded.items():
                    self._data[key] = self._sanitize_value(key, value)
            else:
                log_warning("Using default config (config file does not contain an object)")
        except (OSError, TypeError, ValueError) as e:
            log_warning(f"Using default config ({e})")

    def save(self) -> None:
        """Save configuration to disk atomically."""
        tmp_path = f"{CONFIG_FILE}.tmp"
        try:
            with open(tmp_path, "w") as f:
                json.dump(self._data, f)
            os.rename(tmp_path, CONFIG_FILE)
        except OSError as e:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            log_error(f"Save failed: {e}")

    def __getitem__(self, key: str) -> "Any":
        """Get configuration value by key."""
        if key in self._data:
            return self._sanitize_value(key, self._data[key])
        return self._sanitize_value(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value: "Any") -> None:
        """Set configuration value by key."""
        self._data[key] = self._sanitize_value(key, value)

    def get(self, key: str, default: "Any" = None) -> "Any":
        """Get configuration value with optional default."""
        value = self._data.get(key, default)
        return self._sanitize_value(key, value)


# Singleton instance
settings = Config()
