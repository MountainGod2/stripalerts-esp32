"""Tool exceptions."""

from __future__ import annotations

import shlex


class StripAlertsError(Exception):
    """Base tool exception."""


class PrerequisiteError(StripAlertsError):
    """Prerequisite check failed."""


class DeviceNotFoundError(StripAlertsError):
    """No target device found."""


class BuildError(StripAlertsError):
    """Build failed."""


class FlashError(StripAlertsError):
    """Flash failed."""


class UploadError(StripAlertsError):
    """Upload failed."""


class CommandError(StripAlertsError):
    """Command execution failed."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str | None = None) -> None:
        """Initialize command error with details."""
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message."""
        msg = f"Command failed with exit code {self.returncode}: {shlex.join(self.cmd)}"
        if self.stderr:
            msg += f"\n{self.stderr}"
        return msg


class OperationTimeoutError(StripAlertsError):
    """Operation timed out."""
