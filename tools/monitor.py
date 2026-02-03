"""
Serial monitor for ESP32.
Provides a simple way to connect to the device's REPL.
"""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Monitor ESP32 serial connection")
    parser.add_argument(
        "--port",
        default="/dev/ttyACM0",
        help="Serial port (default: /dev/ttyACM0)",
    )
    parser.add_argument(
        "--device",
        default="a0",
        help="mpremote device shortcut (default: a0)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Baud rate (default: 115200)",
    )

    args = parser.parse_args()

    print(f"Connecting to {args.port} at {args.baud} baud...")
    print("Press Ctrl+] or Ctrl+X to exit\n")

    try:
        # Use mpremote REPL
        subprocess.run(
            ["mpremote", args.device, "repl"],
            check=False,
        )
    except KeyboardInterrupt:
        print("\nDisconnected")
    except FileNotFoundError:
        print("Error: mpremote not found")
        print("Install with: pip install mpremote")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())