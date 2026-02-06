"""Boot script for StripAlerts ESP32."""

import gc
import sys

import esp

esp.osdebug(None)
gc.collect()

print("\n" + "=" * 50)
print("StripAlerts ESP32 - Booting...")
print("=" * 50)

try:
    import machine

    freq_mhz = machine.freq() // 1000000
    print(f"CPU Frequency: {freq_mhz} MHz")
    print(f"Free memory: {gc.mem_free()} bytes")

except Exception as e:
    print(f"Error during boot setup: {e}")
    sys.print_exception(e)

print("Boot complete. Running main.py...\n")
