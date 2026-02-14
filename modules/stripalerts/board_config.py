"""Board-specific configuration."""

import os


def get_board_defaults():
    """Return board-specific defaults based on runtime detection."""
    machine = os.uname().machine
    if "ESP32S3" in machine:
        return {
            "led_pin": 48,
        }
    # Default to original ESP32 board
    return {
        "led_pin": 16,
    }
