#!/usr/bin/env python3
"""StripAlerts ESP32 Development CLI.

Consolidated tool for building, uploading, monitoring, and managing
the StripAlerts ESP32 firmware and application files.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import ClassVar

from utils import (
    check_idf_prerequisites,
    check_tool_available,
    find_serial_port,
    get_chip_type,
    print_header,
    print_success,
    run_command,
)

try:
    import serial
except ImportError:
    print("[ERROR] pyserial not installed")
    print("Install with: pip install pyserial")


class FirmwareBuilder:
    """Builds ESP32 MicroPython firmware with frozen modules."""

    def __init__(self, root_dir: Path, board: str, *, clean: bool = False) -> None:
        """Initialize the firmware builder.

        Args:
            root_dir: Root directory of the project
            board: Target ESP32 board variant
            clean: Whether to clean before building

        """
        self.root_dir = root_dir
        self.firmware_dir = root_dir / "firmware"
        self.micropython_dir = self.firmware_dir / "micropython"
        self.frozen_dir = root_dir / "frozen"
        self.board = board
        self.clean = clean
        self.esp32_port_dir = self.micropython_dir / "ports" / "esp32"
        self.idf_py_cmd = ["idf.py"]

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        print("Checking prerequisites...")

        success, idf_path, idf_cmd = check_idf_prerequisites()
        if not success:
            print("[ERROR] IDF_PATH not set or ESP-IDF not properly configured")
            print("Please source ESP-IDF export.sh or export.bat first")
            return False

        print(f"[OK] ESP-IDF found at: {idf_path}")

        if idf_cmd:
            self.idf_py_cmd = idf_cmd
            print(f"[OK] idf.py command: {' '.join(idf_cmd)}")
        else:
            print("[ERROR] idf.py not found")
            print("Please run: source $IDF_PATH/export.sh")
            return False

        return True

    def setup_micropython(self) -> bool:
        """Clone and setup MicroPython repository if needed."""
        if self.micropython_dir.exists():
            print(f"[OK] MicroPython already cloned at {self.micropython_dir}")
            return True

        print("Cloning MicroPython repository...")
        try:
            run_command(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "https://github.com/micropython/micropython.git",
                    str(self.micropython_dir),
                ],
                cwd=self.firmware_dir,
            )
            print("[OK] MicroPython cloned successfully")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to clone MicroPython: {e}")
            return False
        return True

    def build_mpy_cross(self) -> bool:
        """Build the mpy-cross compiler."""
        mpy_cross_dir = self.micropython_dir / "mpy-cross"
        print("Building mpy-cross compiler...")

        try:
            run_command(["make"], cwd=mpy_cross_dir)
            print("[OK] mpy-cross built successfully")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to build mpy-cross: {e}")
            return False
        return True

    def clean_build(self) -> None:
        """Clean the build directory."""
        build_dir = self.esp32_port_dir / f"build-{self.board}"
        if build_dir.exists():
            print(f"Cleaning build directory: {build_dir}")
            shutil.rmtree(build_dir)
            print("[OK] Build directory cleaned")

    def copy_custom_board(self) -> bool:
        """Copy custom board configuration if it exists."""
        custom_board_src = self.root_dir / "boards" / self.board
        if not custom_board_src.exists():
            return True  # No custom board, use default

        custom_board_dest = self.esp32_port_dir / "boards" / self.board
        print(f"Copying custom board configuration: {self.board}")

        try:
            if custom_board_dest.exists():
                shutil.rmtree(custom_board_dest)
            shutil.copytree(custom_board_src, custom_board_dest)
            print(f"[OK] Custom board copied to {custom_board_dest}")
        except Exception as e:
            print(f"[ERROR] Failed to copy custom board: {e}")
            return False
        return True

    def build_firmware(self) -> bool:
        """Build the ESP32 firmware."""
        print(f"Building firmware for {self.board}...")

        if self.clean:
            self.clean_build()

        if not self.copy_custom_board():
            return False

        try:
            run_command(
                ["make", f"BOARD={self.board}", "submodules"],
                cwd=self.esp32_port_dir,
            )
            run_command(
                ["make", f"BOARD={self.board}"],
                cwd=self.esp32_port_dir,
            )
            print("[OK] Firmware built successfully")
            self.copy_firmware_artifacts()
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to build firmware: {e}")
            return False
        return True

    def copy_firmware_artifacts(self) -> None:
        """Copy firmware artifacts to build directory."""
        build_dir = self.root_dir / "firmware" / "build"
        build_dir.mkdir(parents=True, exist_ok=True)

        board_build_dir = self.esp32_port_dir / f"build-{self.board}"
        firmware_files = {
            "micropython.bin": "firmware.bin",
            "bootloader/bootloader.bin": "bootloader.bin",
            "partition_table/partition-table.bin": "partition-table.bin",
        }

        for src_path, dest_name in firmware_files.items():
            src = board_build_dir / src_path
            if src.exists():
                dest = build_dir / dest_name
                shutil.copy2(src, dest)
                print(f"[OK] Copied {dest_name}")

        # Create versioned firmware
        micropython_bin = board_build_dir / "micropython.bin"
        if micropython_bin.exists():
            version = self._get_version()
            versioned_name = f"stripalerts-{version}-{self.board}.bin"
            shutil.copy2(micropython_bin, build_dir / versioned_name)
            print(f"[OK] Created versioned firmware: {versioned_name}")

    def _get_version(self) -> str:
        """Extract version from pyproject.toml."""
        pyproject_path = self.root_dir / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            match = re.search(r'version\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1)
        return "dev"

    def build(self) -> bool:
        """Execute the complete build process."""
        print_header("StripAlerts ESP32 Firmware Builder")

        if not self.check_prerequisites():
            return False
        if not self.setup_micropython():
            return False
        if not self.build_mpy_cross():
            return False
        if not self.build_firmware():
            return False

        print_success(f"Build completed - {self.root_dir / 'firmware' / 'build'}")
        return True


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
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to erase flash: {e}")
            return False
        return True

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
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to upload firmware: {e}")
            return False
        return True

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
            time.sleep(2)  # Wait for device to stabilize after reset
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Soft reset might fail if device is not responding, continue anyway
            return False
        return True

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
            except subprocess.TimeoutExpired:
                print(
                    f"  [WARNING] Upload timeout (attempt {attempt + 1}/{max_retries})"
                )
                if attempt < max_retries - 1:
                    time.sleep(2)
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
            return True
        return False

    def create_remote_dir(self, remote_path: str, port: str) -> None:
        """Create a directory on the device (ignore if exists)."""
        try:
            cmd = ["mpremote", "connect", port, "fs", "mkdir", f":{remote_path}"]
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass  # Directory might already exist

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

        print_success("All files uploaded")
        return True


class SerialMonitor:
    """Monitors ESP32 serial output."""

    def __init__(self, port: str | None = None, baud: int = 115200) -> None:
        """Initialize the serial monitor.

        Args:
            port: Serial port (auto-detected if None)
            baud: Baud rate for monitoring

        """
        self.port = port
        self.baud = baud

    def monitor(self) -> bool:
        """Execute the monitoring process."""
        port = self.port or find_serial_port()
        if not port:
            print("[ERROR] Could not detect ESP32 device")
            return False

        # Try mpremote first, fallback to pyserial
        if check_tool_available("mpremote"):
            return self._monitor_mpremote(port)
        return self._monitor_pyserial(port)

    def _monitor_mpremote(self, port: str) -> bool:
        """Monitor using mpremote tool."""
        print_header(f"Serial Monitor (mpremote)\nPort: {port} | Baud: {self.baud}")
        print("Press Ctrl+C to exit\n")

        try:
            run_command(["mpremote", "connect", port])
        except (subprocess.CalledProcessError, KeyboardInterrupt):
            print("\n[INFO] Monitoring stopped")
            return True
        return True

    def _monitor_pyserial(self, port: str) -> bool:
        """Monitor using pyserial."""
        print_header(f"Serial Monitor (pyserial)\nPort: {port} | Baud: {self.baud}")
        print("Press Ctrl+C to exit\n")

        try:
            with serial.Serial(port, self.baud, timeout=1) as ser:
                while True:
                    if ser.in_waiting:
                        try:
                            line = (
                                ser.readline()
                                .decode("utf-8", errors="replace")
                                .rstrip()
                            )
                            print(line)
                        except Exception as e:
                            print(f"[ERROR] {e}")
        except KeyboardInterrupt:
            print("\n[INFO] Monitoring stopped")
            return True
        except Exception as e:
            print(f"\n[ERROR] {e}")
            return False


class BuildCleaner:
    """Cleans build artifacts and caches."""

    def __init__(self, root_dir: Path, *, all_clean: bool = False) -> None:
        """Initialize the build cleaner.

        Args:
            root_dir: Root directory of the project
            all_clean: Whether to clean everything including MicroPython

        """
        self.root_dir = root_dir
        self.all_clean = all_clean
        self.firmware_dir = root_dir / "firmware"
        self.build_dir = self.firmware_dir / "build"
        self.micropython_dir = self.firmware_dir / "micropython"

    def clean_build_artifacts(self) -> None:
        """Clean build artifacts."""
        print("Cleaning build artifacts...")

        if self.build_dir.exists():
            print(f"  Removing: {self.build_dir}")
            shutil.rmtree(self.build_dir)
            print("  [OK] Removed build directory")

        if self.micropython_dir.exists():
            esp32_port_dir = self.micropython_dir / "ports" / "esp32"
            if esp32_port_dir.exists():
                for build_dir in esp32_port_dir.glob("build-*"):
                    print(f"  Removing: {build_dir.name}")
                    shutil.rmtree(build_dir)

    def clean_python_cache(self) -> None:
        """Clean Python cache files."""
        print("Cleaning Python cache files...")

        for pattern in ["**/__pycache__", "**/*.pyc", "**/*.pyo", "**/*.pyd"]:
            for path in self.root_dir.glob(pattern):
                if "firmware/micropython" in str(path):
                    continue
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    print(f"  [OK] Removed {path.relative_to(self.root_dir)}")
                except Exception as e:
                    print(f"  [WARNING] Failed to remove {path}: {e}")

    def clean_micropython(self) -> None:
        """Remove MicroPython source directory."""
        if not self.micropython_dir.exists():
            print("MicroPython directory does not exist")
            return

        print(f"Removing MicroPython directory: {self.micropython_dir}")
        try:
            shutil.rmtree(self.micropython_dir)
            print("[OK] MicroPython directory removed")
        except Exception as e:
            print(f"[ERROR] Failed to remove MicroPython: {e}")

    def clean(self) -> bool:
        """Execute the cleaning process."""
        print_header("StripAlerts ESP32 Build Cleaner")

        self.clean_build_artifacts()
        self.clean_python_cache()

        if self.all_clean:
            print("\nPerforming deep clean (including MicroPython)...")
            self.clean_micropython()

        print_success("Clean completed")
        return True


# Command handlers
def cmd_build(args) -> int:
    """Build command handler."""
    root_dir = Path(__file__).parent.parent.resolve()
    builder = FirmwareBuilder(root_dir, args.board, clean=args.clean)
    return 0 if builder.build() else 1


def cmd_flash(args) -> int:
    """Flash firmware command handler."""
    root_dir = Path(__file__).parent.parent.resolve()
    uploader = FirmwareUploader(
        root_dir, args.board, args.port, args.baud, erase=args.erase
    )
    return 0 if uploader.upload() else 1


def cmd_upload(args) -> int:
    """Upload application files command handler."""
    root_dir = Path(__file__).parent.parent.resolve()
    uploader = FileUploader(root_dir, args.port)
    return 0 if uploader.upload_files() else 1


def cmd_monitor(args) -> int:
    """Monitor command handler."""
    monitor = SerialMonitor(args.port, args.baud)
    return 0 if monitor.monitor() else 1


def cmd_clean(args) -> int:
    """Clean command handler."""
    root_dir = Path(__file__).parent.parent.resolve()
    cleaner = BuildCleaner(root_dir, all_clean=args.all)
    return 0 if cleaner.clean() else 1


def cmd_deploy(args) -> int:
    """Deploy command handler (build + flash + upload + monitor)."""
    root_dir = Path(__file__).parent.parent.resolve()

    # Step 1: Build
    if not args.skip_build:
        print_header("STEP 1: Building Firmware")
        builder = FirmwareBuilder(root_dir, args.board, clean=args.clean)
        if not builder.build():
            print("\n[ERROR] Build failed")
            return 1

    # Step 2: Flash firmware
    if not args.skip_flash:
        print_header("STEP 2: Flashing Firmware")
        uploader = FirmwareUploader(
            root_dir, args.board, args.port, args.baud, erase=args.erase
        )
        if not uploader.upload():
            print("\n[ERROR] Flash failed")
            return 1

    # Step 3: Upload application files
    if not args.skip_upload:
        print_header("STEP 3: Uploading Application Files")
        # Wait for device to stabilize after flashing
        print("Waiting for device to stabilize...")
        time.sleep(3)
        file_uploader = FileUploader(root_dir, args.port)
        if not file_uploader.upload_files():
            print("\n[ERROR] File upload failed")
            return 1

    # Step 4: Monitor
    if not args.skip_monitor:
        print_header("STEP 4: Monitoring Device")
        monitor = SerialMonitor(args.port, 115200)
        monitor.monitor()

    print_success("Deployment completed")
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="StripAlerts ESP32 Development CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build firmware")
    build_parser.add_argument(
        "--board",
        default="ESP32_GENERIC_S3",
        help="ESP32 board variant (default: ESP32_GENERIC_S3)",
    )
    build_parser.add_argument(
        "--clean", action="store_true", help="Clean before building"
    )
    build_parser.set_defaults(func=cmd_build)

    # Flash command
    flash_parser = subparsers.add_parser("flash", help="Flash firmware to device")
    flash_parser.add_argument(
        "--port", "-p", help="Serial port (auto-detect if not set)"
    )
    flash_parser.add_argument(
        "--baud", "-b", type=int, default=460800, help="Baud rate"
    )
    flash_parser.add_argument(
        "--board", default="ESP32_GENERIC_S3", help="ESP32 board variant"
    )
    flash_parser.add_argument("--erase", action="store_true", help="Erase flash first")
    flash_parser.set_defaults(func=cmd_flash)

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload application files")
    upload_parser.add_argument(
        "--port", "-p", help="Serial port (auto-detect if not set)"
    )
    upload_parser.set_defaults(func=cmd_upload)

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor serial output")
    monitor_parser.add_argument(
        "--port", "-p", help="Serial port (auto-detect if not set)"
    )
    monitor_parser.add_argument(
        "--baud", "-b", type=int, default=115200, help="Baud rate"
    )
    monitor_parser.set_defaults(func=cmd_monitor)

    # Clean command
    clean_parser = subparsers.add_parser("clean", help="Clean build artifacts")
    clean_parser.add_argument(
        "--all", action="store_true", help="Clean everything including MicroPython"
    )
    clean_parser.set_defaults(func=cmd_clean)

    # Deploy command
    deploy_parser = subparsers.add_parser(
        "deploy", help="Full deployment (build + flash + upload + monitor)"
    )
    deploy_parser.add_argument(
        "--port", "-p", help="Serial port (auto-detect if not set)"
    )
    deploy_parser.add_argument(
        "--board", default="ESP32_GENERIC_S3", help="ESP32 board variant"
    )
    deploy_parser.add_argument(
        "--baud", type=int, default=460800, help="Flash baud rate"
    )
    deploy_parser.add_argument(
        "--clean", action="store_true", help="Clean before building"
    )
    deploy_parser.add_argument("--erase", action="store_true", help="Erase flash first")
    deploy_parser.add_argument(
        "--skip-build", action="store_true", help="Skip build step"
    )
    deploy_parser.add_argument(
        "--skip-flash", action="store_true", help="Skip flash step"
    )
    deploy_parser.add_argument(
        "--skip-upload", action="store_true", help="Skip upload step"
    )
    deploy_parser.add_argument(
        "--skip-monitor", action="store_true", help="Skip monitor step"
    )
    deploy_parser.set_defaults(func=cmd_deploy)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
