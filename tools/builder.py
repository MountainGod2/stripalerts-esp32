"""Firmware builder."""

from __future__ import annotations

import re
import shutil
from typing import TYPE_CHECKING

from .console import (
    StatusLogger,
    print_file_operation,
    print_header,
    print_info,
    print_keyval,
    print_success,
    print_warning,
)
from .device import check_idf_environment
from .exceptions import BuildError, CommandError, OperationTimeoutError
from .subprocess_utils import run_command

if TYPE_CHECKING:
    from .config import BuildConfig, ProjectPaths


class FirmwareBuilder:
    """Builds ESP32 MicroPython firmware with frozen modules."""

    def __init__(self, config: BuildConfig, paths: ProjectPaths) -> None:
        """Initialize firmware builder."""
        self.config = config
        self.paths = paths

    def check_prerequisites(self) -> None:
        """Verify ESP-IDF installation and configuration."""
        with StatusLogger("Checking prerequisites"):
            idf_path, idf_cmd = check_idf_environment()
            print_keyval("ESP-IDF Path", idf_path)
            print_keyval("idf.py Command", " ".join(idf_cmd))

    def setup_micropython(self) -> None:
        """Initialize MicroPython git submodule if needed."""
        marker_file = self.paths.micropython / "py" / "mpconfig.h"
        if marker_file.exists():
            print_info(f"MicroPython submodule already initialized at {self.paths.micropython}")
            return

        with StatusLogger("Initializing MicroPython submodule"):
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
                    cwd=self.paths.root,
                    verbose=self.config.verbose,
                )
            except (CommandError, OperationTimeoutError, OSError) as e:
                msg = f"Failed to initialize MicroPython submodule: {e}"
                raise BuildError(msg) from e

    def build_mpy_cross(self) -> None:
        """Build mpy-cross compiler if missing."""
        mpy_cross_bin = self.paths.mpy_cross / "build" / "mpy-cross"

        if mpy_cross_bin.exists():
            print_info("mpy-cross already built")
            return

        with StatusLogger("Building mpy-cross compiler"):
            try:
                run_command(
                    ["make", "CC=gcc"],
                    cwd=self.paths.mpy_cross,
                    verbose=self.config.verbose,
                    timeout=None,
                )
            except (CommandError, OperationTimeoutError, OSError) as e:
                msg = f"Failed to build mpy-cross: {e}"
                raise BuildError(msg) from e

    def clean_build_artifacts(self) -> None:
        """Remove existing build and dist directories."""
        build_dir = self.paths.build_dir(self.config.board)

        if build_dir.exists():
            print_info(f"Cleaning build directory: {build_dir}")
            shutil.rmtree(build_dir)
            print_file_operation("Removed", str(build_dir))

        if self.paths.dist.exists():
            print_info(f"Cleaning dist directory: {self.paths.dist}")
            shutil.rmtree(self.paths.dist)
            print_file_operation("Removed", str(self.paths.dist))

    def build_firmware(self) -> None:
        """Build MicroPython firmware with frozen modules."""
        with StatusLogger(f"Building firmware for {self.config.board}"):
            if self.config.clean:
                self.clean_build_artifacts()

            make_args = [f"BOARD={self.config.board}"]

            board_dir = self.paths.board_dir(self.config.board)
            if board_dir.exists():
                print_info(f"Using custom board definition from: {board_dir}")
                make_args.append(f"BOARD_DIR={board_dir}")

            try:
                run_command(
                    ["make", *make_args, "submodules"],
                    cwd=self.paths.micropython_esp32,
                    verbose=self.config.verbose,
                    timeout=None,
                )

                run_command(
                    ["make", *make_args],
                    cwd=self.paths.micropython_esp32,
                    verbose=self.config.verbose,
                    timeout=None,
                )

                self._copy_firmware_artifacts()

            except (CommandError, OperationTimeoutError, OSError) as e:
                msg = f"Failed to build firmware: {e}"
                raise BuildError(msg) from e

    def _copy_firmware_artifacts(self) -> None:
        """Copy bootloader, partition table, and firmware to dist/."""
        self.paths.dist.mkdir(parents=True, exist_ok=True)

        build_dir = self.paths.build_dir(self.config.board)

        firmware_files = {
            "micropython.bin": "firmware.bin",
            "bootloader/bootloader.bin": "bootloader.bin",
            "partition_table/partition-table.bin": "partition-table.bin",
        }

        for src_rel, dest_name in firmware_files.items():
            src = build_dir / src_rel
            if src.exists():
                dest = self.paths.dist / dest_name
                shutil.copy2(src, dest)
                print_file_operation("Copied", dest_name)
            else:
                print_warning(f"Firmware file not found: {src_rel}")

        micropython_bin = build_dir / "micropython.bin"
        if micropython_bin.exists():
            version = self._get_version()
            versioned_name = f"stripalerts-{version}-{self.config.board}.bin"
            shutil.copy2(micropython_bin, self.paths.dist / versioned_name)
            print_file_operation("Created", versioned_name)

    def _get_version(self) -> str:
        """Extract version from `pyproject.toml`."""
        pyproject_path = self.paths.root / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            match = re.search(r'version\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1)
        return "dev"

    def build(self) -> None:
        """Execute complete build workflow."""
        print_header("StripAlerts ESP32 Firmware Builder", f"Board: {self.config.board}")

        self.check_prerequisites()
        self.setup_micropython()
        self.build_mpy_cross()
        self.build_firmware()

        print_success(f"Build completed - artifacts in {self.paths.dist}")
