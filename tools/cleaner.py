"""Build cleaner for StripAlerts ESP32."""

from __future__ import annotations

import shutil
from pathlib import Path

from utils import print_header, print_success


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
