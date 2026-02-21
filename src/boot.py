"""Boot script for StripAlerts ESP32."""

import gc
import os
import sys
import time

import esp

esp.osdebug(None)
gc.collect()

CONFIG_FILE = "/config.json"
BOOT_BUTTON_PIN = 0
BUTTON_DEBOUNCE_MS = 50
HARD_RESET_HOLD_MS = 5000


def _is_boot_button_pressed() -> bool:
    """Return True when built-in BOOT button is pressed.

    BOOT buttons on ESP32/ESP32-S3 boards are typically active-low on GPIO0.
    """
    try:
        import machine

        button = machine.Pin(BOOT_BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
        return button.value() == 0
    except Exception as e:
        print(f"BOOT button check unavailable: {e}")
        return False


def _wipe_config() -> None:
    """Delete persisted user configuration file if it exists."""
    try:
        os.remove(CONFIG_FILE)
        print(f"Removed {CONFIG_FILE}")
    except OSError:
        print(f"No {CONFIG_FILE} found; nothing to remove")


def _handle_hard_reset() -> None:
    """Detect and execute long-press hard reset during boot."""
    if not _is_boot_button_pressed():
        return

    print("BOOT button pressed. Hold for 5s to factory reset...")
    time.sleep_ms(BUTTON_DEBOUNCE_MS)
    if not _is_boot_button_pressed():
        print("Button bounce detected, continuing normal boot")
        return

    start = time.ticks_ms()
    while _is_boot_button_pressed():
        elapsed = time.ticks_diff(time.ticks_ms(), start)
        if elapsed >= HARD_RESET_HOLD_MS:
            print("Factory reset confirmed")
            _wipe_config()
            print("Restarting device...")
            import machine

            machine.reset()
            return
        time.sleep_ms(100)

    print("Factory reset canceled (button released too early)")


print("\n" + "=" * 50)
print("StripAlerts ESP32 - Booting...")
print("=" * 50)

_handle_hard_reset()

try:
    import machine

    freq_mhz = machine.freq() // 1000000
    print(f"CPU Frequency: {freq_mhz} MHz")
    print(f"Free memory: {gc.mem_free()} bytes")

except Exception as e:
    print(f"Error during boot setup: {e}")
    sys.print_exception(e)

print("Boot complete. Running main.py...\n")
