"""Modern serial monitor for ESP32 devices."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .console import console, print_header, print_info, print_warning
from .device import check_pyserial, get_or_find_port
from .subprocess_utils import check_command_available, run_interactive

if TYPE_CHECKING:
    from .config import MonitorConfig

try:
    import serial
except ImportError as e:
    msg = "pyserial is required for serial monitoring"
    raise ImportError(msg) from e


class SerialMonitor:
    """Monitors ESP32 serial output."""

    def __init__(self, config: MonitorConfig) -> None:
        """Initialize serial monitor.

        Args:
            config: Monitor configuration
        """
        self.config = config

    def monitor(self) -> None:
        """Start monitoring serial output (mpremote or pyserial)."""
        port = get_or_find_port(self.config.port)

        if check_command_available("mpremote"):
            self._monitor_mpremote(port)
        elif check_pyserial():
            self._monitor_pyserial(port)
        else:
            print_warning("Neither mpremote nor pyserial available")
            print_info("Install with: uv sync")

    def _monitor_mpremote(self, port: str) -> None:
        """Monitor serial output using mpremote."""
        # mpremote uses a fixed baud rate (115200), so self.config.baud is ignored
        print_header("Serial Monitor (mpremote)", f"Port: {port}")
        print_info("Press Ctrl+C to exit\n")

        try:
            run_interactive(["mpremote", "connect", port])
        except KeyboardInterrupt:
            print_info("Monitoring stopped")

    def _monitor_pyserial(self, port: str) -> None:
        """Monitor serial output using pyserial library."""
        print_header("Serial Monitor (pyserial)", f"Port: {port} | Baud: {self.config.baud}")
        print_info("Press Ctrl+C to exit\n")

        try:
            with serial.Serial(port, self.config.baud, timeout=1) as ser:
                while True:
                    if ser.in_waiting:
                        try:
                            line = ser.readline().decode("utf-8", errors="replace").rstrip()
                            console.print(line)
                        except (serial.SerialException, UnicodeDecodeError) as e:
                            print_warning(f"Read error: {e}")
                    else:
                        time.sleep(0.01)
        except KeyboardInterrupt:
            print_info("Monitoring stopped")
        except (serial.SerialException, OSError) as e:
            print_warning(f"Monitor error: {e}")
