"""Common utilities for StripAlerts ESP32 development tools."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def find_serial_port() -> str | None:
    """Auto-detect ESP32 serial port.

    Returns:
        Serial port path if found, None otherwise
    """
    print("Auto-detecting ESP32 device...")

    try:
        result = subprocess.run(
            ["python", "-m", "esptool", "chip_id"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "Serial port" in line:
                    port = line.split()[-1]
                    print(f"[OK] Found ESP32 on port: {port}")
                    return port
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    ports = [
        str(p)
        for pattern in ["ttyUSB*", "ttyACM*", "cu.usb*", "cu.wchusbserial*"]
        for p in Path("/dev").glob(pattern)
    ]

    if ports:
        port = ports[0]
        print(f"[OK] Using port: {port}")
        return port

    print("[ERROR] No ESP32 device found")
    return None


def check_idf_prerequisites() -> tuple[bool, str | None, list[str]]:
    """Check ESP-IDF prerequisites.

    Returns:
        Tuple of (success, idf_path, idf_py_command)

    """
    esp_idf_path = os.environ.get("IDF_PATH")
    if not esp_idf_path:
        return False, None, []

    try:
        result = subprocess.run(
            ["idf.py", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return True, esp_idf_path, ["idf.py"]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    idf_py_path = Path(esp_idf_path) / "tools" / "idf.py"
    if idf_py_path.exists():
        try:
            result = subprocess.run(
                ["python3", str(idf_py_path), "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode == 0:
                return True, esp_idf_path, ["python3", str(idf_py_path)]
        except subprocess.TimeoutExpired:
            pass

    return False, esp_idf_path, []


def check_tool_available(tool: str, version_flag: str = "--version") -> bool:
    """Check if a command-line tool is available.

    Args:
        tool: Tool name or command
        version_flag: Flag to check version (default: --version)

    Returns:
        True if tool is available, False otherwise
    """
    try:
        result = subprocess.run(
            [tool, version_flag],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return result.returncode == 0


def run_command(
    cmd: list[str],
    cwd: str | Path | None = None,
    env: dict | None = None,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a command with error handling.

    Args:
        cmd: Command and arguments
        cwd: Working directory
        env: Environment variables
        check: Raise exception on non-zero return code

    Returns:
        CompletedProcess instance

    Raises:
        subprocess.CalledProcessError: If check=True and command fails

    """
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=check)


def get_chip_type(board: str) -> str:
    """Determine ESP32 chip type from board name.

    Args:
        board: Board variant name

    Returns:
        Chip type string for esptool

    """
    board_upper = board.upper()
    if "S3" in board_upper:
        return "esp32s3"
    if "S2" in board_upper:
        return "esp32s2"
    if "C3" in board_upper:
        return "esp32c3"
    if "C6" in board_upper:
        return "esp32c6"
    if "H2" in board_upper:
        return "esp32h2"
    return "esp32"


def print_header(title: str, width: int = 60) -> None:
    """Print a formatted header.

    Args:
        title: Header title
        width: Total width of header

    """
    print("\n" + "=" * width)
    print(title)
    print("=" * width + "\n")


def print_success(message: str, width: int = 60) -> None:
    """Print a success message with formatting.

    Args:
        message: Success message
        width: Total width of box

    """
    print("\n" + "=" * width)
    print(f"[SUCCESS] {message}")
    print("=" * width)
