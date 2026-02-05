"""Configuration management for StripAlerts."""

import json

CONFIG_FILE = "/config.json"

class Config:
    def __init__(self):
        self._config = {}
        self.load()

    def load(self):
        """Load configuration from JSON file."""
        try:
            with open(CONFIG_FILE, "r") as f:
                self._config = json.load(f)
        except (OSError, ValueError):
            # File missing or invalid, use defaults/empty
            pass

    def get(self, key, default=None):
        """Get a configuration value."""
        return self._config.get(key, default)

# Singleton instance
settings = Config()
