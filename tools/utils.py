"""Common utilities for StripAlerts ESP32 development tools."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def find_serial_port() -> str | None:
    """Auto-detect ESP32 serial port via esptool or /dev scanning."""
    print("Auto-detecting ESP32 device...")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "esptool", "chip_id"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "Serial port" in line:
                    port = line.split()[-1].rstrip(":")
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
    """Check ESP-IDF installation and return (success, idf_path, idf_py_command)."""
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
                [sys.executable, str(idf_py_path), "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode == 0:
                return True, esp_idf_path, [sys.executable, str(idf_py_path)]
        except subprocess.TimeoutExpired:
            pass

    return False, esp_idf_path, []


def check_tool_available(tool: str, version_flag: str = "--version") -> bool:
    """Check if command-line tool is available by running version check."""
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
    """Run command with optional working directory and environment."""
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=check)


def get_chip_type(board: str) -> str:
    """Map board name to esptool chip type (esp32, esp32s3, etc.)."""
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
    """Print formatted header with title."""
    print("\n" + "=" * width)
    print(title)
    print("=" * width + "\n")


def print_success(message: str, width: int = 60) -> None:
    """Print formatted success message."""
    print("\n" + "=" * width)
    print(f"[SUCCESS] {message}")
    print("=" * width)


def get_root_dir() -> Path:
    """Get project root directory (assumes tools/utils.py location)."""
    return Path(__file__).parent.parent.resolve()


def check_mpremote() -> bool:
    """Check if mpremote is installed and available."""
    if not check_tool_available("mpremote"):
        print("[ERROR] mpremote not found")
        print("Install with: uv sync")
        return False
    return True


def soft_reset_device(port: str) -> bool:
    """Soft-reset device to restart and run uploaded code."""
    try:
        cmd = ["mpremote", "connect", port, "soft-reset"]
        subprocess.run(cmd, check=True, timeout=5, capture_output=True)
        time.sleep(1)
        return True
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as e:
        print(f"[WARNING] Soft reset failed: {e}")
        return False
