"""Firmware and file uploaders for StripAlerts ESP32."""

from __future__ import annotations

import subprocess
import sys
import time
from typing import TYPE_CHECKING, ClassVar

from utils import (
    check_mpremote,
    find_serial_port,
    get_chip_type,
    print_header,
    print_success,
    run_command,
    soft_reset_device,
)

if TYPE_CHECKING:
    from pathlib import Path


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
        """Initialize firmware uploader for ESP32 board variant."""
        self.root_dir = root_dir
        self.port = port
        self.baud = baud
        self.board = board
        self.erase = erase
        self.dist_dir = root_dir / "dist"
        self.chip = get_chip_type(board)

    def check_firmware_files(self) -> bool:
        """Verify required firmware files exist in dist/."""
        print("Checking firmware files...")

        if not self.dist_dir.exists():
            print(f"[ERROR] Dist directory not found: {self.dist_dir}")
            print("Run 'build' command first")
            return False

        required_files = ["bootloader.bin", "partition-table.bin", "firmware.bin"]
        missing = [f for f in required_files if not (self.dist_dir / f).exists()]

        if missing:
            print(f"[ERROR] Missing firmware files: {', '.join(missing)}")
            print("Please rebuild firmware")
            return False

        print("[OK] All firmware files found")
        return True

    def erase_flash(self, port: str) -> bool:
        """Erase device flash memory via esptool."""
        print("Erasing flash memory...")
        try:
            run_command(
                [sys.executable, "-m", "esptool", "--port", port, "erase-flash"]
            )
            print("[OK] Flash erased successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to erase flash: {e}")
            return False

    def upload_firmware(self, port: str) -> bool:
        """Flash bootloader, partition table, and firmware to device."""
        print(f"Uploading firmware to {port} at {self.baud} baud...")

        cmd = [
            sys.executable,
            "-m",
            "esptool",
            "--chip",
            self.chip,
            "--port",
            port,
            "--baud",
            str(self.baud),
            "write-flash",
            "-z",
            hex(self.FLASH_ADDRESSES["bootloader"]),
            str(self.dist_dir / "bootloader.bin"),
            hex(self.FLASH_ADDRESSES["partition-table"]),
            str(self.dist_dir / "partition-table.bin"),
            hex(self.FLASH_ADDRESSES["firmware"]),
            str(self.dist_dir / "firmware.bin"),
        ]

        try:
            run_command(cmd)
            print("[OK] Firmware uploaded successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to upload firmware: {e}")
            return False

    def upload(self) -> bool:
        """Execute complete firmware upload workflow."""
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
        """Initialize file uploader for application code."""
        self.root_dir = root_dir
        self.src_dir = root_dir / "src"
        self.port = port

    def upload_file(self, port: str, local_path: Path, remote_path: str) -> bool:
        """Upload single file with interrupt and retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                cmd = [
                    "mpremote",
                    "connect",
                    port,
                    "exec",
                    "",
                    "fs",
                    "cp",
                    str(local_path),
                    f":{remote_path}",
                ]
                subprocess.run(cmd, check=True, capture_output=True, timeout=30)
                return True
            except subprocess.TimeoutExpired:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                print(f"    [ERROR] Timeout uploading {local_path.name}")
                return False
            except subprocess.CalledProcessError as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    print(f"    [ERROR] Failed to upload {local_path.name}")
                    if e.stderr:
                        stderr = e.stderr.decode("utf-8", errors="ignore").strip()
                        if stderr:
                            print(f"    {stderr}")
                    return False
        return False

    def upload_files_batch(self, port: str, files: list[tuple[Path, str]]) -> bool:
        """Upload multiple files sequentially, interrupting program before each."""
        if not files:
            return True

        print(f"\nUploading {len(files)} file(s)...")
        for local_path, remote_path in files:
            print(f"  {local_path.name} -> {remote_path}", end=" ", flush=True)
            if not self.upload_file(port, local_path, remote_path):
                return False
            print("[OK]")

        return True

    def upload_files(self) -> bool:
        """Upload boot.py, main.py, and config.json, then soft-reset device."""
        print_header("StripAlerts Application File Uploader")

        if not check_mpremote():
            return False

        port = self.port or find_serial_port()
        if not port:
            print("[ERROR] Could not detect ESP32 device")
            return False

        if not self.src_dir.exists():
            print(f"[ERROR] Source directory not found: {self.src_dir}")
            return False

        print(f"Preparing to upload files from {self.src_dir}...")

        files_to_upload: list[tuple[Path, str]] = []

        for filename in ["boot.py", "main.py"]:
            file_path = self.src_dir / filename
            if file_path.exists():
                files_to_upload.append((file_path, f"/{filename}"))
            else:
                print(f"[WARNING] {filename} not found, skipping")

        config_file = self.root_dir / "config.json"
        example_config = self.root_dir / "config.json.example"

        if config_file.exists():
            files_to_upload.append((config_file, "/config.json"))
        elif example_config.exists():
            print(f"[INFO] config.json not found, using {example_config.name}")
            files_to_upload.append((example_config, "/config.json"))
        else:
            print("[WARNING] No config file found, skipping")

        if not files_to_upload:
            print("[ERROR] No files to upload")
            return False

        if not self.upload_files_batch(port, files_to_upload):
            return False

        print("\nRestarting device to run uploaded code...")
        if soft_reset_device(port):
            print("[OK] Device restarted successfully")
        else:
            print("[INFO] Please manually reset the device to run new code")

        print_success("All files uploaded")
        return True
