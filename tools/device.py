"""ESP32 device detection and control."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None

from .console import print_info, print_success, print_warning
from .exceptions import CommandError, DeviceNotFoundError, OperationTimeoutError, PrerequisiteError
from .subprocess_utils import check_command_available, get_command_output, run_command

ESP32_VID_PIDS = [(0x10C4, 0xEA60), (0x1A86, 0x7523), (0x303A, None)]


class ESP32Device:
    """ESP32 serial connection wrapper."""

    def __init__(self, port: str) -> None:
        """Initialize device with port."""
        self.port = port

    def soft_reset(self, timeout: int = 5) -> bool:
        """Restart device so boot.py/main.py run."""
        commands = [
            self._mpremote_cmd("exec", "import machine; machine.reset()"),
            self._mpremote_cmd("soft-reset"),
        ]

        for index, cmd in enumerate(commands):
            if not self._run_mpremote(
                cmd,
                timeout=timeout,
                check=False,
                allow_disconnect_success=index == 0,
            ):
                continue

            time.sleep(1)
            print_success(f"Device on {self.port} reset successfully")
            return True

        print_warning(f"Reset failed on {self.port}")
        return False

    def interrupt_program(self, timeout: int = 5) -> bool:
        """Interrupt a running program."""
        return self._run_mpremote(
            self._mpremote_cmd("exec", ""),
            timeout=timeout,
        )

    def remove_file(self, remote_path: str, timeout: int = 5) -> bool:
        """Remove a file from device filesystem."""
        cmd = self._mpremote_cmd("fs", "rm", f":{remote_path}")
        return self._run_mpremote(cmd, timeout=timeout, check=False)

    def copy_file(self, local_path: str, remote_path: str, timeout: int = 30) -> bool:
        """Copy a local file to device filesystem."""
        cmd = self._mpremote_cmd("fs", "cp", local_path, f":{remote_path}")
        return self._run_mpremote(cmd, timeout=timeout, check=False)

    def _mpremote_cmd(self, *args: str) -> list[str]:
        """Build an mpremote command for this device."""
        return ["mpremote", "connect", self.port, *args]

    def _run_mpremote(
        self,
        cmd: list[str],
        timeout: int,
        *,
        check: bool = True,
        allow_disconnect_success: bool = False,
    ) -> bool:
        """Run an mpremote command and return success."""
        try:
            result = run_command(
                cmd,
                timeout=timeout,
                capture_output=True,
                check=check,
            )
        except (OSError, CommandError, OperationTimeoutError):
            return False

        if not check:
            if result.returncode != 0 and allow_disconnect_success:
                print_warning("mpremote disconnected during reset; treating as successful reset")
                return True
            return result.returncode == 0
        return True


def _find_esp32_via_esptool() -> str | None:
    """Try to find ESP32 device using esptool."""
    output = get_command_output([sys.executable, "-m", "esptool", "chip_id"])
    if not output:
        return None

    for line in output.split("\n"):
        if "Serial port" in line:
            port = line.split()[-1].rstrip(":")
            print_success(f"Found ESP32 on port: {port}")
            return port
    return None


def _find_esp32_via_serial_ports() -> str | None:
    """Try to find ESP32 device using pyserial list_ports."""
    if list_ports is None:
        return None

    for port_info in list_ports.comports():
        for vid, pid in ESP32_VID_PIDS:
            if port_info.vid == vid and (pid is None or port_info.pid == pid):
                print_success(f"Found ESP32 on port: {port_info.device}")
                return port_info.device
    return None


def _find_esp32_via_dev_patterns() -> str | None:
    """Try to find ESP32 device by searching /dev patterns (Unix-like systems)."""
    if sys.platform == "win32":
        return None

    patterns = ["ttyUSB*", "ttyACM*", "cu.usb*", "cu.wchusbserial*"]
    ports = sorted(str(p) for pattern in patterns for p in Path("/dev").glob(pattern))
    if ports:
        port = ports[0]
        print_warning(f"Using port: {port} (pattern-based guess)")
        return port
    return None


def find_esp32_device() -> str:
    """Auto-detect ESP32 serial port."""
    print_info("Auto-detecting ESP32 device...")

    for finder in [
        _find_esp32_via_serial_ports,
        _find_esp32_via_dev_patterns,
    ]:
        port = finder()
        if port:
            return port

    if list_ports is not None:
        all_ports_info = list(list_ports.comports())
        if all_ports_info:
            port = all_ports_info[0].device
            print_warning(
                f"No ESP32 VID/PID match found; using first available port as fallback: {port}",
            )
            return port

    port = _find_esp32_via_esptool()
    if port:
        return port

    msg = "No ESP32 device found. Please connect device or specify --port"
    raise DeviceNotFoundError(msg)


def get_or_find_port(port: str | None) -> str:
    """Return specified port or auto-detect one."""
    if port:
        print_info(f"Using specified port: {port}")
        return port
    return find_esp32_device()


def check_mpremote() -> None:
    """Ensure `mpremote` is available."""
    if not check_command_available("mpremote"):
        msg = "mpremote not found. Install with: uv sync"
        raise PrerequisiteError(msg)


def check_idf_environment() -> tuple[Path, list[str]]:
    """Validate ESP-IDF environment and return `(idf_path, idf_cmd)`."""
    esp_idf_path = os.environ.get("IDF_PATH")
    if not esp_idf_path:
        msg = (
            "IDF_PATH not set. Run: source ~/esp/esp-idf/export.sh "
            "(adjust path to your ESP-IDF installation)"
        )
        raise PrerequisiteError(msg)

    idf_path = Path(esp_idf_path)

    if check_command_available("idf.py"):
        print_success(f"ESP-IDF found at: {idf_path}")
        return idf_path, ["idf.py"]

    idf_py_path = idf_path / "tools" / "idf.py"
    if idf_py_path.exists():
        cmd = [sys.executable, str(idf_py_path)]
        output = get_command_output([*cmd, "--version"])
        if output:
            print_success(f"ESP-IDF found at: {idf_path}")
            return idf_path, cmd
        msg = (
            f"idf.py found at {idf_py_path} but could not be executed. "
            "Check file permissions and that Python can run it. "
            "You may need to run: source ~/esp/esp-idf/export.sh"
        )
        raise PrerequisiteError(msg)

    msg = (
        "idf.py not found. Run: source ~/esp/esp-idf/export.sh "
        "(adjust path to your ESP-IDF installation)"
    )
    raise PrerequisiteError(msg)


def check_pyserial() -> bool:
    """Return whether pyserial is available."""
    return list_ports is not None
