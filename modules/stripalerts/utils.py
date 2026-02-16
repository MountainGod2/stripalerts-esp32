"""Utility functions and helpers."""

import time


def log(level: str, message: str) -> None:
    """Log message with timestamp and level.

    Args:
        level: Log level (INFO, WARNING, ERROR, DEBUG)
        message: Message to log

    """
    timestamp = time.localtime()
    print(
        f"[{timestamp[3]:02d}:{timestamp[4]:02d}:{timestamp[5]:02d}] "
        f"[{level}] {message}"
    )


def log_info(message: str) -> None:
    """Log info message."""
    log("INFO", message)


def log_error(message: str) -> None:
    """Log error message."""
    log("ERROR", message)


def log_warning(message: str) -> None:
    """Log warning message."""
    log("WARNING", message)
