"""Device detection and management for ESP32."""

from __future__ import annotations

import os
import subprocess
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
    """Represents an ESP32 device connection."""

    def __init__(self, port: str) -> None:
        """Initialize device with port."""
        self.port = port

    def soft_reset(self, timeout: int = 5) -> bool:
        """Soft-reset device to restart application.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if reset successful
        """
        try:
            run_command(
                ["mpremote", "connect", self.port, "soft-reset"],
                timeout=timeout,
                capture_output=True,
            )
            time.sleep(1)
            print_success(f"Device on {self.port} reset successfully")
        except (subprocess.SubprocessError, OSError, CommandError, OperationTimeoutError) as e:
            print_warning(f"Soft reset failed: {e}")
            return False
        else:
            return True

    def interrupt_program(self, timeout: int = 5) -> bool:
        """Interrupt running program with Ctrl+C.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if interrupt successful
        """
        try:
            run_command(
                ["mpremote", "connect", self.port, "exec", ""],
                timeout=timeout,
                capture_output=True,
            )
        except (subprocess.SubprocessError, OSError, CommandError, OperationTimeoutError):
            return False
        else:
            return True

    def remove_file(self, remote_path: str, timeout: int = 5) -> bool:
        """Remove file from device filesystem.

        Args:
            remote_path: Remote file path
            timeout: Timeout in seconds

        Returns:
            True if removal successful
        """
        try:
            result = run_command(
                ["mpremote", "connect", self.port, "fs", "rm", f":{remote_path}"],
                timeout=timeout,
                capture_output=True,
                check=False,
            )
        except (subprocess.SubprocessError, OSError):
            return False
        else:
            return result.returncode == 0


def _find_esp32_via_esptool() -> str | None:
    """Try to find ESP32 device using esptool.

    Returns:
        Port path or None if not found
    """
    output = get_command_output([sys.executable, "-m", "esptool", "chip_id"])
    if output:
        for line in output.split("\n"):
            if "Serial port" in line:
                port = line.split()[-1].rstrip(":")
                print_success(f"Found ESP32 on port: {port}")
                return port
    return None


def _find_esp32_via_serial_ports() -> str | None:
    """Try to find ESP32 device using pyserial list_ports.

    Returns:
        Port path or None if not found
    """
    if list_ports is None:
        return None

    all_ports_info = list(list_ports.comports())
    for port_info in all_ports_info:
        for vid, pid in ESP32_VID_PIDS:
            if port_info.vid == vid and (pid is None or port_info.pid == pid):
                print_success(f"Found ESP32 on port: {port_info.device}")
                return port_info.device

    if all_ports_info:
        port = all_ports_info[0].device
        print_success(f"Using port: {port}")
        return port
    return None


def _find_esp32_via_dev_patterns() -> str | None:
    """Try to find ESP32 device by searching /dev patterns (Unix-like systems).

    Returns:
        Port path or None if not found
    """
    if sys.platform == "win32":
        return None

    patterns = ["ttyUSB*", "ttyACM*", "cu.usb*", "cu.wchusbserial*"]
    ports = [str(p) for pattern in patterns for p in Path("/dev").glob(pattern)]
    if ports:
        port = ports[0]
        print_success(f"Using port: {port}")
        return port
    return None


def find_esp32_device() -> str:
    """Auto-detect ESP32 device serial port.

    Returns:
        Serial port path

    Raises:
        DeviceNotFoundError: If no device found
    """
    print_info("Auto-detecting ESP32 device...")

    # Try multiple detection strategies
    for finder in [
        _find_esp32_via_esptool,
        _find_esp32_via_serial_ports,
        _find_esp32_via_dev_patterns,
    ]:
        port = finder()
        if port:
            return port

    msg = "No ESP32 device found. Please connect device or specify --port"
    raise DeviceNotFoundError(msg)


def get_or_find_port(port: str | None) -> str:
    """Get specified port or auto-detect.

    Args:
        port: Optional port specification

    Returns:
        Port path

    Raises:
        DeviceNotFoundError: If no device found
    """
    if port:
        print_info(f"Using specified port: {port}")
        return port
    return find_esp32_device()


def check_mpremote() -> None:
    """Check if mpremote is installed.

    Raises:
        PrerequisiteError: If mpremote not available
    """
    if not check_command_available("mpremote"):
        msg = "mpremote not found. Install with: uv sync"
        raise PrerequisiteError(msg)


def check_esptool() -> None:
    """Check if esptool is installed.

    Raises:
        PrerequisiteError: If esptool not available
    """
    output = get_command_output([sys.executable, "-m", "esptool", "version"])
    if output:
        return

    if not check_command_available("esptool.py"):
        msg = "esptool not found. Install with: uv sync or python -m pip install esptool"
        raise PrerequisiteError(msg)


def check_idf_environment() -> tuple[Path, list[str]]:
    """Check ESP-IDF installation and configuration.

    Returns:
        Tuple of (idf_path, idf_py_command)

    Raises:
        PrerequisiteError: If ESP-IDF not properly configured
    """
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
        "idf.py not found. Run: source ~/esp/esp-idf/export.sh "
        "(adjust path to your ESP-IDF installation)"
    )
    raise PrerequisiteError(msg)


def check_pyserial() -> bool:
    """Check if pyserial is available.

    Uses the module-level list_ports import as the single source of truth.

    Returns:
        True if pyserial is available
    """
    return list_ports is not None
