"""Firmware and file uploaders for StripAlerts ESP32."""

from __future__ import annotations

try:
    from typing import ClassVar
except ImportError:
    pass

import subprocess
import time
from pathlib import Path
from typing import ClassVar

from utils import (
    check_tool_available,
    find_serial_port,
    get_chip_type,
    print_header,
    print_success,
    run_command,
)


class FirmwareUploader:
    """Uploads firmware to ESP32 devices."""

    FLASH_ADDRESSES: ClassVar = {
        "bootloader": 0x0,
        "partition-table": 0x8000,
        "firmware": 0x10000,
    }

    def __init__(
        self,
        root_dir: Path,
        board: str,
        port: str | None = None,
        baud: int = 460800,
        *,
        erase: bool = False,
    ) -> None:
        """Initialize the firmware uploader.

        Args:
            root_dir: Root directory of the project
            board: Target ESP32 board variant
            port: Serial port (auto-detected if None)
            baud: Baud rate for flashing
            erase: Whether to erase flash before uploading

        """
        self.root_dir = root_dir
        self.port = port
        self.baud = baud
        self.board = board
        self.erase = erase
        self.build_dir = root_dir / "firmware" / "build"
        self.chip = get_chip_type(board)

    def check_firmware_files(self) -> bool:
        """Verify that required firmware files exist."""
        print("Checking firmware files...")

        if not self.build_dir.exists():
            print(f"[ERROR] Build directory not found: {self.build_dir}")
            print("Run 'build' command first")
            return False

        required_files = ["bootloader.bin", "partition-table.bin", "firmware.bin"]
        missing = [f for f in required_files if not (self.build_dir / f).exists()]

        if missing:
            print(f"[ERROR] Missing firmware files: {', '.join(missing)}")
            print("Please rebuild firmware")
            return False

        print("[OK] All firmware files found")
        return True

    def erase_flash(self, port: str) -> bool:
        """Erase the flash memory."""
        print("Erasing flash memory...")
        try:
            run_command(["python", "-m", "esptool", "--port", port, "erase_flash"])
            print("[OK] Flash erased successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to erase flash: {e}")
            return False

    def upload_firmware(self, port: str) -> bool:
        """Upload firmware to device."""
        print(f"Uploading firmware to {port} at {self.baud} baud...")

        cmd = [
            "python",
            "-m",
            "esptool",
            "--chip",
            self.chip,
            "--port",
            port,
            "--baud",
            str(self.baud),
            "write_flash",
            "-z",
            hex(self.FLASH_ADDRESSES["bootloader"]),
            str(self.build_dir / "bootloader.bin"),
            hex(self.FLASH_ADDRESSES["partition-table"]),
            str(self.build_dir / "partition-table.bin"),
            hex(self.FLASH_ADDRESSES["firmware"]),
            str(self.build_dir / "firmware.bin"),
        ]

        try:
            run_command(cmd)
            print("[OK] Firmware uploaded successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to upload firmware: {e}")
            return False

    def upload(self) -> bool:
        """Execute the upload process."""
        print_header("StripAlerts ESP32 Firmware Uploader")

        if not self.check_firmware_files():
            return False

        port = self.port or find_serial_port()
        if not port:
            print("[ERROR] Could not detect ESP32 device")
            print("Specify port with --port option")
            return False

        if self.erase and not self.erase_flash(port):
            return False

        if not self.upload_firmware(port):
            return False

        print_success("Firmware upload completed")
        return True


class FileUploader:
    """Uploads application files to ESP32 filesystem."""

    def __init__(self, root_dir: Path, port: str | None = None) -> None:
        """Initialize the file uploader.

        Args:
            root_dir: Root directory of the project
            port: Serial port (auto-detected if None)

        """
        self.root_dir = root_dir
        self.src_dir = root_dir / "src"
        self.port = port

    def check_mpremote(self) -> bool:
        """Check if mpremote is available."""
        if not check_tool_available("mpremote"):
            print("[ERROR] mpremote not found")
            print("Install with: pip install mpremote")
            return False
        print("[OK] mpremote found")
        return True

    def soft_reset_device(self, port: str) -> bool:
        """Perform a soft reset on the device to ensure clean REPL state."""
        try:
            cmd = ["mpremote", "connect", port, "soft-reset"]
            subprocess.run(cmd, check=True, capture_output=True, timeout=5)
            time.sleep(2)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    def upload_file(self, local_path: Path, remote_path: str, port: str) -> bool:
        """Upload a single file to the device with retry logic."""
        print(f"  Uploading {local_path.name} -> {remote_path}")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                cmd = [
                    "mpremote",
                    "connect",
                    port,
                    "fs",
                    "cp",
                    str(local_path),
                    f":{remote_path}",
                ]
                subprocess.run(cmd, check=True, capture_output=True, timeout=30)
                return True
            except subprocess.TimeoutExpired:
                print(
                    f"  [WARNING] Upload timeout (attempt {attempt + 1}/{max_retries})"
                )
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                print(
                    f"  [ERROR] Failed to upload {local_path.name} after {max_retries} attempts"
                )
                return False
            except subprocess.CalledProcessError:
                if attempt < max_retries - 1:
                    print(
                        f"  [WARNING] Upload failed (attempt {attempt + 1}/{max_retries}), retrying..."
                    )
                    time.sleep(2)
                else:
                    print(
                        f"  [ERROR] Failed to upload {local_path.name} after {max_retries} attempts"
                    )
                    return False
        return False

    def create_remote_dir(self, remote_path: str, port: str) -> None:
        """Create a directory on the device (ignore if exists)."""
        try:
            cmd = ["mpremote", "connect", port, "fs", "mkdir", f":{remote_path}"]
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass

    def upload_files(self) -> bool:
        """Upload all application files to device."""
        print_header("StripAlerts Application File Uploader")

        if not self.check_mpremote():
            return False

        port = self.port or find_serial_port()
        if not port:
            print("[ERROR] Could not detect ESP32 device")
            return False

        if not self.src_dir.exists():
            print(f"[ERROR] Source directory not found: {self.src_dir}")
            return False

        print(f"Uploading files from {self.src_dir}...")
        print("\nPerforming soft reset to ensure clean state...")
        self.soft_reset_device(port)

        # Upload boot.py and main.py
        for filename in ["boot.py", "main.py"]:
            file_path = self.src_dir / filename
            if file_path.exists() and not self.upload_file(
                file_path, f"/{filename}", port
            ):
                return False

        # Handle configuration file
        config_file = self.root_dir / "config.json"
        example_config = self.root_dir / "config.json.example"

        if config_file.exists():
            if not self.upload_file(config_file, "/config.json", port):
                return False
        elif example_config.exists():
            print(f"config.json not found, using {example_config.name}")
            if not self.upload_file(example_config, "/config.json", port):
                return False

        print_success("All files uploaded")
        return True
