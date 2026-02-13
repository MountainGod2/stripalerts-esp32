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

    def __init__(
        self,
        root_dir: Path,
        board: str,
        *,
        clean: bool = False,
        output_dir: Path | None = None,
    ) -> None:
        """Initialize the firmware builder.

        Args:
            root_dir: Root directory of the project
            board: Target ESP32 board variant
            clean: Whether to clean before building
            output_dir: Optional directory to copy firmware artifacts to

        """
        self.root_dir = root_dir
        self.firmware_dir = root_dir / "firmware"
        self.micropython_dir = root_dir / "micropython"
        self.lib_dir = root_dir / "modules"
        self.board = board
        self.clean = clean
        self.esp32_port_dir = self.micropython_dir / "ports" / "esp32"
        self.idf_py_cmd = ["idf.py"]
        self.output_dir = output_dir or (root_dir / "firmware" / "build")

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
        """Initialize MicroPython submodule if needed."""
        # Check if submodule is populated
        if (self.micropython_dir / "py" / "mpconfig.h").exists():
            print(
                f"[OK] MicroPython submodule seems populated at {self.micropython_dir}"
            )
            return True

        print("Initializing MicroPython submodule...")
        try:
            run_command(
                [
                    "git",
                    "submodule",
                    "update",
                    "--init",
                    "--recursive",
                    "micropython",
                ],
                cwd=self.root_dir,
            )
            print("[OK] MicroPython submodule initialized")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to initialize MicroPython submodule: {e}")
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

    def build_firmware(self) -> bool:
        """Build the ESP32 firmware."""
        print(f"Building firmware for {self.board}...")

        if self.clean:
            self.clean_build()

        make_args = [f"BOARD={self.board}"]

        # Check for custom board directory
        custom_board_path = self.root_dir / "boards" / self.board
        if custom_board_path.exists():
            print(f"Using custom board definition from: {custom_board_path}")
            make_args.append(f"BOARD_DIR={custom_board_path}")

        try:
            run_command(
                ["make"] + make_args + ["submodules"],
                cwd=self.esp32_port_dir,
            )
            run_command(
                ["make"] + make_args,
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
        build_dir = self.output_dir
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
