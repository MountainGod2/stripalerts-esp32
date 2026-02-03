#!/usr/bin/env python3
"""
Monitor script for StripAlerts ESP32 firmware.

This script monitors the serial output from an ESP32 device.
"""

import argparse
import sys


class SerialMonitor:
    """Handles monitoring of ESP32 serial output."""

    def __init__(
        self,
        port: str | None = None,
        baud: int = 115200,
        filter_text: str | None = None,
    ):
        """Initialize the serial monitor.

        Args:
            port: Serial port (auto-detected if None)
            baud: Baud rate for serial communication
            filter_text: Optional text filter for output
        """
        self.port = port
        self.baud = baud
        self.filter_text = filter_text

    def find_port(self) -> str | None:
        """Auto-detect the ESP32 serial port."""
        print("Auto-detecting ESP32 device...")

        try:
            import glob

            # Linux/macOS
            ports = (
                glob.glob("/dev/ttyUSB*")
                + glob.glob("/dev/ttyACM*")
                + glob.glob("/dev/cu.usb*")
            )

            if ports:
                port = ports[0]
                print(f"[OK] Using port: {port}")
                return port

            print("[ERROR] No serial device found")
            return None

        except Exception as e:
            print(f"[WARNING] Auto-detection failed: {e}")
            return None

    def monitor_mpremote(self, port: str) -> bool:
        """Monitor using mpremote tool."""
        import subprocess

        print("=" * 60)
        print("StripAlerts ESP32 Serial Monitor (mpremote)")
        print(f"Port: {port} | Baud: {self.baud}")
        print("=" * 60)
        print("Press Ctrl+C to exit\n")

        try:
            cmd = ["mpremote", "connect", port]
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            print("\n[INFO] Monitoring stopped")
            return False
        except KeyboardInterrupt:
            print("\n\n[INFO] Monitoring stopped by user")
            return True

    def monitor_pyserial(self, port: str) -> bool:
        """Monitor using pyserial."""
        try:
            import serial
        except ImportError:
            print("[ERROR] pyserial not installed")
            print("Install with: pip install pyserial")
            return False

        print("=" * 60)
        print("StripAlerts ESP32 Serial Monitor (pyserial)")
        print(f"Port: {port} | Baud: {self.baud}")
        if self.filter_text:
            print(f"Filter: {self.filter_text}")
        print("=" * 60)
        print("Press Ctrl+C to exit\n")

        try:
            with serial.Serial(port, self.baud, timeout=1) as ser:
                while True:
                    if ser.in_waiting:
                        try:
                            line = (
                                ser.readline()
                                .decode("utf-8", errors="replace")
                                .rstrip()
                            )
                            if line:
                                if self.filter_text is None or self.filter_text in line:
                                    print(line)
                        except Exception as e:
                            print(f"[WARNING] Error reading line: {e}")
        except serial.SerialException as e:
            print(f"\n[ERROR] Serial error: {e}")
            return False
        except KeyboardInterrupt:
            print("\n\n[INFO] Monitoring stopped by user")
            return True

    def monitor(self) -> bool:
        """Execute the monitoring process."""
        # Determine port
        port = self.port
        if not port:
            port = self.find_port()
            if not port:
                print("\n[ERROR] Could not detect serial device")
                print("Please specify port with --port option")
                return False

        # Try mpremote first, fall back to pyserial
        try:
            import subprocess

            result = subprocess.run(
                ["mpremote", "--version"], capture_output=True, check=False
            )
            if result.returncode == 0:
                return self.monitor_mpremote(port)
        except FileNotFoundError:
            pass

        # Use pyserial as fallback
        return self.monitor_pyserial(port)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor StripAlerts ESP32 serial output"
    )
    parser.add_argument(
        "--port", "-p", help="Serial port (auto-detected if not specified)"
    )
    parser.add_argument(
        "--baud", "-b", type=int, default=115200, help="Baud rate (default: 115200)"
    )
    parser.add_argument(
        "--filter", "-f", dest="filter_text", help="Filter output containing this text"
    )

    args = parser.parse_args()

    # Create and run the monitor
    monitor = SerialMonitor(
        port=args.port, baud=args.baud, filter_text=args.filter_text
    )

    success = monitor.monitor()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
