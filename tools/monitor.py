"""Serial monitor for ESP32 devices."""

from __future__ import annotations

import subprocess

from utils import check_tool_available, find_serial_port, print_header, run_command

try:
    import serial
except ImportError:
    serial = None


class SerialMonitor:
    """Monitors ESP32 serial output."""

    def __init__(self, port: str | None = None, baud: int = 115200) -> None:
        """Initialize the serial monitor.

        Args:
            port: Serial port (auto-detected if None)
            baud: Baud rate for monitoring
        """
        self.port = port
        self.baud = baud

    def monitor(self) -> bool:
        """Execute the monitoring process."""
        port = self.port or find_serial_port()
        if not port:
            print("[ERROR] Could not detect ESP32 device")
            return False

        # Try mpremote first, fallback to pyserial
        if check_tool_available("mpremote"):
            return self._monitor_mpremote(port)
        return self._monitor_pyserial(port)

    def _monitor_mpremote(self, port: str) -> bool:
        """Monitor using mpremote tool."""
        print_header(f"Serial Monitor (mpremote)\nPort: {port} | Baud: {self.baud}")
        print("Press Ctrl+C to exit\n")

        try:
            run_command(["mpremote", "connect", port])
        except (subprocess.CalledProcessError, KeyboardInterrupt):
            print("\n[INFO] Monitoring stopped")
            return True
        return True

    def _monitor_pyserial(self, port: str) -> bool:
        """Monitor using pyserial."""
        if serial is None:
            print("[ERROR] pyserial not installed")
            print("Install with: pip install pyserial")
            return False

        print_header(f"Serial Monitor (pyserial)\nPort: {port} | Baud: {self.baud}")
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
                            print(line)
                        except Exception as e:
                            print(f"[ERROR] {e}")
        except KeyboardInterrupt:
            print("\n[INFO] Monitoring stopped")
            return True
        except Exception as e:
            print(f"\n[ERROR] {e}")
            return False
