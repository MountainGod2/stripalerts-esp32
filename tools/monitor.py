"""
Serial monitor for StripAlerts ESP32.
Connects to ESP32 and displays serial output.
"""

import sys
import serial
import argparse


def monitor(port="/dev/ttyUSB0", baud=115200):
    """Monitor serial output from ESP32."""

    print("=" * 60)
    print("StripAlerts Serial Monitor")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Baud: {baud}")
    print("Press Ctrl+C to exit")
    print("=" * 60)
    print()

    try:
        ser = serial.Serial(port, baud, timeout=1)

        while True:
            if ser.in_waiting > 0:
                data = ser.readline()
                try:
                    print(data.decode("utf-8"), end="")
                except UnicodeDecodeError:
                    print(data)

    except KeyboardInterrupt:
        print("\n\nMonitor closed.")

    except serial.SerialException as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor StripAlerts ESP32")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")

    args = parser.parse_args()
    sys.exit(monitor(args.port, args.baud))
