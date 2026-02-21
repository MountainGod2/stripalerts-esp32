"""Serial monitor."""

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
except ImportError:
    serial = None


EXIT_SIGINT = 130


class SerialMonitor:
    """Monitors ESP32 serial output."""

    def __init__(self, config: MonitorConfig) -> None:
        """Initialize serial monitor."""
        self.config = config

    def monitor(self) -> None:
        """Start monitoring serial output."""
        port = get_or_find_port(self.config.port)
        if check_pyserial():
            self._monitor_pyserial(port)
        elif check_command_available("mpremote"):
            print_info("pyserial unavailable, falling back to mpremote interactive monitor")
            self._monitor_mpremote(port)
        else:
            print_warning("Neither mpremote nor pyserial available")
            print_info("Install with: uv sync")

    def _monitor_mpremote(self, port: str) -> None:
        """Monitor serial output using mpremote."""
        print_header("Serial Monitor (mpremote)", f"Port: {port}")
        print_info("Press Ctrl+C to exit\n")

        exit_code = run_interactive(["mpremote", "connect", port])
        if exit_code == EXIT_SIGINT:
            print_info("Monitoring stopped")
        elif exit_code != 0:
            print_warning(f"Monitor exited with status {exit_code}")

    def _monitor_pyserial(self, port: str) -> None:
        """Monitor serial output using pyserial library."""
        print_header("Serial Monitor (pyserial)", f"Port: {port} | Baud: {self.config.baud}")
        print_info("Press Ctrl+C to exit\n")

        try:
            with serial.Serial(port, self.config.baud, timeout=1) as ser:
                self._start_application(ser)

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

    def _start_application(self, ser: "serial.Serial") -> None:
        """Ensure app starts if board is at REPL."""
        try:
            ser.reset_input_buffer()
            ser.write(b"\x03")
            ser.write(b"\x04")
            ser.flush()
            time.sleep(0.25)
        except (serial.SerialException, OSError):
            pass
