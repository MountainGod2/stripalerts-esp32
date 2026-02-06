"""Utility functions and helpers."""

import time
import gc
import sys
import esp32
import micropython


def log(level: str, message: str) -> None:
    """Simple logging function.

    Args:
        level: Log level (INFO, WARNING, ERROR, DEBUG)
        message: Message to log
    """
    timestamp = time.localtime()
    print(
        f"[{timestamp[3]:02d}:{timestamp[4]:02d}:{timestamp[5]:02d}] [{level}] {message}"
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


def log_debug(message: str) -> None:
    """Log debug message."""
    log("DEBUG", message)


@micropython.native
def format_mac(mac_bytes: bytes) -> str:
    """Format MAC address bytes as string.

    Args:
        mac_bytes: MAC address bytes

    Returns:
        Formatted MAC address string
    """
    return ":".join("{:02x}".format(b) for b in mac_bytes)


def free_memory() -> int:
    """Get free memory in bytes.

    Returns:
        Free memory in bytes
    """
    gc.collect()
    return gc.mem_free()


def get_mcu_temperature() -> float:
    """Get MCU internal temperature.

    Returns:
        Temperature in Celsius for ESP32-S3/S2/C3/C6, or Fahrenheit for original ESP32
    """
    try:
        if hasattr(esp32, "mcu_temperature"):
            return esp32.mcu_temperature()
        # Original ESP32 has raw_temperature() in Fahrenheit
        elif hasattr(esp32, "raw_temperature"):
            return esp32.raw_temperature()
        else:
            return 0.0
    except Exception:
        return 0.0


def system_info() -> dict:
    """Get system information.

    Returns:
        Dictionary with system information
    """
    info = {
        "platform": sys.platform,
        "version": sys.version,
        "free_mem": free_memory(),
        "mcu_temp": get_mcu_temperature(),
    }

    # Add flash_size if available
    if hasattr(esp32, "flash_size"):
        info["flash_size"] = esp32.flash_size()

    return info
