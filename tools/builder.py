"""Firmware builder for StripAlerts ESP32."""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import TYPE_CHECKING

from utils import check_idf_prerequisites, print_header, print_success, run_command

if TYPE_CHECKING:
    from pathlib import Path


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
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to clone MicroPython: {e}")
            return False

    def build_mpy_cross(self) -> bool:
        """Build the mpy-cross compiler."""
        mpy_cross_dir = self.micropython_dir / "mpy-cross"
        mpy_cross_bin = mpy_cross_dir / "build" / "mpy-cross"

        if mpy_cross_bin.exists():
            print("[OK] mpy-cross already built")
            return True

        print("Building mpy-cross compiler...")

        try:
            run_command(["make", "CC=gcc"], cwd=mpy_cross_dir)
            print("[OK] mpy-cross built successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to build mpy-cross: {e}")
            return False

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
            return True
        except Exception as e:
            print(f"[ERROR] Failed to copy custom board: {e}")
            return False

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
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to build firmware: {e}")
            return False

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
