"""Modern firmware and file uploaders for StripAlerts ESP32."""

from __future__ import annotations

import sys
from pathlib import Path

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
from .exceptions import FlashError, UploadError
from .subprocess_utils import retry, run_command


class FirmwareUploader:
    """Uploads firmware to ESP32 devices."""

    def __init__(self, config: FlashingConfig, paths: ProjectPaths) -> None:
        """Initialize firmware uploader.

        Args:
            config: Flashing configuration
            paths: Project paths
        """
        self.config = config
        self.paths = paths

    def check_firmware_files(self) -> None:
        """Verify required firmware files exist in dist/.

        Raises:
            FlashError: If firmware files are missing
        """
        if not self.paths.dist.exists():
            raise FlashError(
                f"Dist directory not found: {self.paths.dist}\nRun 'build' command first"
            )

        required_files = ["bootloader.bin", "partition-table.bin", "firmware.bin"]
        missing = [f for f in required_files if not (self.paths.dist / f).exists()]

        if missing:
            raise FlashError(
                f"Missing firmware files: {', '.join(missing)}\nPlease rebuild firmware"
            )

        print_success("All firmware files found")

    def erase_flash(self, port: str) -> None:
        """Erase device flash memory.

        Args:
            port: Serial port

        Raises:
            FlashError: If erase fails
        """
        with StatusLogger("Erasing flash memory"):
            try:
                run_command(
                    [sys.executable, "-m", "esptool", "--port", port, "erase-flash"],
                    verbose=True,
                )
            except Exception as e:
                raise FlashError(f"Failed to erase flash: {e}") from e

    def upload_firmware(self, port: str) -> None:
        """Flash bootloader, partition table, and firmware to device.

        Args:
            port: Serial port

        Raises:
            FlashError: If flashing fails
        """
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
            except Exception as e:
                raise FlashError(f"Failed to upload firmware: {e}") from e

    def upload(self) -> None:
        """Execute complete firmware upload workflow.

        Raises:
            FlashError: If upload fails
        """
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
        """Initialize file uploader.

        Args:
            config: Upload configuration
            paths: Project paths
        """
        self.config = config
        self.paths = paths

    @retry()
    def upload_file(self, device: ESP32Device, local_path: Path, remote_path: str) -> None:
        """Upload single file with automatic retry.

        Args:
            device: ESP32 device
            local_path: Local file path
            remote_path: Remote file path

        Raises:
            UploadError: If upload fails after retries
        """
        cmd = [
            "mpremote",
            "connect",
            device.port,
            "exec",
            "",
            "fs",
            "cp",
            str(local_path),
            f":{remote_path}",
        ]

        try:
            run_command(cmd, timeout=30, capture_output=True)
            print_file_operation("Uploaded", f"{local_path.name} → {remote_path}")
        except Exception as e:
            raise UploadError(f"Failed to upload {local_path.name}: {e}") from e

    def prepare_device(self, device: ESP32Device) -> None:
        """Prepare device by interrupting program and clearing old files.

        Args:
            device: ESP32 device
        """
        print_info("Interrupting any running application...")
        device.interrupt_program()

        print_info("Clearing old application files...")
        old_files = ["/boot.py", "/main.py", "/config.json"]
        for file_path in old_files:
            device.remove_file(file_path)

    def collect_files(self) -> list[tuple[Path, str]]:
        """Collect files to upload.

        Returns:
            List of (local_path, remote_path) tuples

        Raises:
            UploadError: If no files to upload
        """
        if not self.paths.src.exists():
            raise UploadError(f"Source directory not found: {self.paths.src}")

        files_to_upload: list[tuple[Path, str]] = []

        # Upload boot.py and main.py
        for filename in self.config.files:
            file_path = self.paths.src / filename
            if file_path.exists():
                files_to_upload.append((file_path, f"/{filename}"))
            else:
                print_warning(f"{filename} not found, skipping")

        # Upload config.json
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
            raise UploadError("No files to upload")

        return files_to_upload

    def upload_files(self) -> None:
        """Upload application files and restart device.

        Raises:
            UploadError: If upload fails
        """
        print_header("StripAlerts Application File Uploader")

        check_mpremote()
        port = get_or_find_port(self.config.port)
        device = ESP32Device(port)

        self.prepare_device(device)
        files = self.collect_files()

        print_info(f"Preparing to upload {len(files)} file(s)...")

        with progress_bar("Uploading files") as progress:
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
