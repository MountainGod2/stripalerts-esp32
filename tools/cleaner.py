"""Modern build cleaner for StripAlerts ESP32."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from .console import (
    StatusLogger,
    print_file_operation,
    print_header,
    print_info,
    print_success,
    print_warning,
)
from .exceptions import CommandError
from .subprocess_utils import check_command_available, run_command

if TYPE_CHECKING:
    from .config import ProjectPaths


class BuildCleaner:
    """Cleans build artifacts and caches."""

    def __init__(self, paths: ProjectPaths, *, deep_clean: bool = False) -> None:
        """Initialize build cleaner.

        Args:
            paths: Project paths
            deep_clean: Whether to perform deep clean including MicroPython
        """
        self.paths = paths
        self.deep_clean = deep_clean

    def clean_build_artifacts(self) -> None:
        """Remove dist/ and build-* directories."""
        with StatusLogger("Cleaning build artifacts"):
            # Clean dist directory
            if self.paths.dist.exists():
                print_info(f"Removing: {self.paths.dist}")
                try:
                    shutil.rmtree(self.paths.dist)
                    print_file_operation("Removed", str(self.paths.dist))
                except OSError as e:
                    print_warning(f"Failed to remove {self.paths.dist}: {e}")

            # Clean ESP32 build directories
            if self.paths.micropython_esp32.exists():
                dirs_to_clean = list(self.paths.micropython_esp32.glob("build-*"))
                build_dir = self.paths.micropython_esp32 / "build"
                if build_dir.exists():
                    dirs_to_clean.append(build_dir)

                for build_dir in dirs_to_clean:
                    if build_dir.is_dir():
                        print_info(f"Removing: {build_dir.name}")
                        try:
                            shutil.rmtree(build_dir)
                            print_file_operation("Removed", build_dir.name)
                        except OSError as e:
                            print_warning(f"Failed to remove {build_dir.name}: {e}")

    def clean_python_cache(self) -> None:
        """Remove __pycache__ and *.pyc files."""
        with StatusLogger("Cleaning Python cache files"):
            patterns = ["**/__pycache__", "**/*.pyc", "**/*.pyo", "**/*.pyd"]

            for pattern in patterns:
                for path in self.paths.root.glob(pattern):
                    # Skip micropython submodule
                    if "micropython" in str(path):
                        continue

                    try:
                        if path.is_dir():
                            shutil.rmtree(path)
                        else:
                            path.unlink()
                        rel_path = path.relative_to(self.paths.root)
                        print_file_operation("Removed", str(rel_path))
                    except OSError as e:
                        print_warning(f"Failed to remove {path}: {e}")

    def clean_micropython(self) -> None:
        """Run 'make clean' in mpy-cross and esp32 port directories."""
        if not self.paths.micropython.exists():
            print_info("MicroPython directory not found, skipping")
            return

        with StatusLogger("Cleaning MicroPython artifacts"):
            # Clean mpy-cross
            if (self.paths.mpy_cross / "Makefile").exists():
                try:
                    print_info("Cleaning mpy-cross...")
                    run_command(["make", "clean"], cwd=self.paths.mpy_cross)
                    print_file_operation("Cleaned", "mpy-cross")
                except (CommandError, OSError) as e:
                    print_warning(f"Failed to clean mpy-cross: {e}")

            # Clean ESP32 port
            if (self.paths.micropython_esp32 / "Makefile").exists():
                if not check_command_available("idf.py"):
                    print_info("idf.py not found, skipping ESP32 port clean")
                else:
                    try:
                        print_info("Cleaning ESP32 port...")
                        run_command(["make", "clean"], cwd=self.paths.micropython_esp32)
                        print_file_operation("Cleaned", "esp32 port")
                    except (CommandError, OSError) as e:
                        print_warning(f"Failed to clean ESP32 port: {e}")

    def clean(self) -> None:
        """Execute full cleaning workflow."""
        print_header("StripAlerts ESP32 Build Cleaner")

        self.clean_build_artifacts()
        self.clean_python_cache()

        if self.deep_clean:
            print_info("Performing deep clean (including MicroPython)...")
            self.clean_micropython()

        print_success("Clean completed")
