"""Custom exceptions for StripAlerts ESP32 tools."""

from __future__ import annotations


class StripAlertsError(Exception):
    """Base exception for all StripAlerts tool errors."""


class PrerequisiteError(StripAlertsError):
    """Raised when prerequisites are not met."""


class DeviceNotFoundError(StripAlertsError):
    """Raised when ESP32 device cannot be found."""


class BuildError(StripAlertsError):
    """Raised when firmware build fails."""


class FlashError(StripAlertsError):
    """Raised when flashing firmware fails."""


class UploadError(StripAlertsError):
    """Raised when file upload fails."""


class CleanError(StripAlertsError):
    """Raised when cleaning fails."""


class CommandError(StripAlertsError):
    """Raised when a command execution fails."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str | None = None):
        """Initialize command error with details."""
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message."""
        msg = f"Command failed with exit code {self.returncode}: {' '.join(self.cmd)}"
        if self.stderr:
            msg += f"\n{self.stderr}"
        return msg


class TimeoutError(StripAlertsError):
    """Raised when an operation times out."""


class ConfigurationError(StripAlertsError):
    """Raised when configuration is invalid."""
