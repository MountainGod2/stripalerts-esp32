"""Firmware and file uploaders."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from .config import FlashConfig, FlashingConfig, ProjectPaths, UploadConfig
from .console import (
    StatusLogger,
    print_file_operation,
    print_header,
    print_info,
    print_success,
    print_warning,
    progress_bar,
)
from .device import ESP32Device, check_mpremote, get_or_find_port
from .exceptions import CommandError, FlashError, OperationTimeoutError, UploadError
from .subprocess_utils import retry, run_command

if TYPE_CHECKING:
    from pathlib import Path


class FirmwareUploader:
    """Uploads firmware to ESP32 devices."""

    def __init__(self, config: FlashingConfig, paths: ProjectPaths) -> None:
        """Initialize firmware uploader."""
        self.config = config
        self.paths = paths

    def check_firmware_files(self) -> None:
        """Verify required firmware files exist in `dist/`."""
        if not self.paths.dist.exists():
            msg = f"Dist directory not found: {self.paths.dist}\nRun 'build' command first"
            raise FlashError(msg)

        required_files = ["bootloader.bin", "partition-table.bin", "firmware.bin"]
        missing = [f for f in required_files if not (self.paths.dist / f).exists()]

        if missing:
            msg = f"Missing firmware files: {', '.join(missing)}\nPlease rebuild firmware"
            raise FlashError(msg)

        print_success("All firmware files found")

    def erase_flash(self, port: str) -> None:
        """Erase device flash memory."""
        with StatusLogger("Erasing flash memory"):
            try:
                run_command(
                    [sys.executable, "-m", "esptool", "--port", port, "erase-flash"],
                    verbose=True,
                )
            except (CommandError, OperationTimeoutError, OSError) as e:
                msg = f"Failed to erase flash: {e}"
                raise FlashError(msg) from e

    def upload_firmware(self, port: str) -> None:
        """Flash bootloader, partition table, and firmware."""
        with StatusLogger(f"Uploading firmware to {port} at {self.config.baud} baud"):
            cmd = [
                sys.executable,
                "-m",
                "esptool",
                "--chip",
                self.config.chip_type.value,
                "--port",
                port,
                "--baud",
                str(self.config.baud),
                "write-flash",
                "-z",
                hex(FlashConfig.get_bootloader_addr(self.config.chip_type)),
                str(self.paths.dist / "bootloader.bin"),
                hex(FlashConfig.PARTITION_TABLE_ADDR),
                str(self.paths.dist / "partition-table.bin"),
                hex(FlashConfig.FIRMWARE_ADDR),
                str(self.paths.dist / "firmware.bin"),
            ]

            try:
                run_command(cmd, verbose=True)
            except (CommandError, OperationTimeoutError, OSError) as e:
                msg = f"Failed to upload firmware: {e}"
                raise FlashError(msg) from e

    def upload(self) -> None:
        """Execute firmware upload workflow."""
        print_header("StripAlerts ESP32 Firmware Uploader", f"Board: {self.config.board}")

        self.check_firmware_files()
        port = get_or_find_port(self.config.port)

        if self.config.erase:
            self.erase_flash(port)

        self.upload_firmware(port)
        print_success("Firmware upload completed")


class FileUploader:
    """Uploads application files to ESP32 filesystem."""

    def __init__(self, config: UploadConfig, paths: ProjectPaths) -> None:
        """Initialize file uploader."""
        self.config = config
        self.paths = paths

    @retry(exceptions=(UploadError,))
    def upload_file(self, device: ESP32Device, local_path: Path, remote_path: str) -> None:
        """Upload one file, with retry."""
        if not device.copy_file(str(local_path), remote_path, timeout=30):
            msg = f"Failed to upload {local_path.name}"
            raise UploadError(msg)

        print_file_operation("Uploaded", f"{local_path.name} → {remote_path}")

    def prepare_device(self, device: ESP32Device) -> None:
        """Interrupt app and remove old files."""
        print_info("Interrupting any running application...")
        if not device.interrupt_program():
            print_warning("Could not interrupt running program, continuing")

        print_info("Clearing old application files...")

        old_files = [f"/{filename}" for filename in self.config.files] + ["/config.json"]

        for file_path in old_files:
            device.remove_file(file_path)

    def collect_files(self) -> list[tuple[Path, str]]:
        """Collect `(local_path, remote_path)` upload pairs."""
        if not self.paths.src.exists():
            msg = f"Source directory not found: {self.paths.src}"
            raise UploadError(msg)

        files_to_upload: list[tuple[Path, str]] = []

        for filename in self.config.files:
            file_path = self.paths.src / filename
            if file_path.exists():
                files_to_upload.append((file_path, f"/{filename}"))
            else:
                print_warning(f"{filename} not found, skipping")

        config_file = self.paths.root / "config.json"
        example_config = self.paths.root / "config.json.example"

        if config_file.exists():
            files_to_upload.append((config_file, "/config.json"))
        elif example_config.exists():
            print_info(f"config.json not found, using {example_config.name}")
            files_to_upload.append((example_config, "/config.json"))
        else:
            print_warning("No config file found, skipping")

        if not files_to_upload:
            msg = "No files to upload"
            raise UploadError(msg)

        return files_to_upload

    def upload_files(self) -> None:
        """Upload application files and restart device."""
        print_header("StripAlerts Application File Uploader")

        check_mpremote()
        port = get_or_find_port(self.config.port)
        device = ESP32Device(port)

        self.prepare_device(device)
        files = self.collect_files()

        print_info(f"Preparing to upload {len(files)} file(s)...")

        with progress_bar() as progress:
            task = progress.add_task("Uploading...", total=len(files))
            for local_path, remote_path in files:
                self.upload_file(device, local_path, remote_path)
                progress.advance(task)

        print_info("Restarting device to run uploaded code...")
        if device.soft_reset():
            print_success("Device restarted successfully")
        else:
            print_warning("Please manually reset the device to run new code")

        print_success("All files uploaded")
