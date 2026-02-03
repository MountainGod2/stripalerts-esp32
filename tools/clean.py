#!/usr/bin/env python3
"""
Clean script for StripAlerts ESP32 firmware build artifacts.

This script removes build artifacts and temporary files.
"""

import argparse
import shutil
import sys
from pathlib import Path


class BuildCleaner:
    """Handles cleaning of build artifacts."""

    def __init__(self, root_dir: Path, all_clean: bool = False):
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

        # Clean the build directory
        if self.build_dir.exists():
            print(f"  Removing: {self.build_dir}")
            shutil.rmtree(self.build_dir)
            print(f"  [OK] Removed {self.build_dir}")

        # Clean MicroPython build directories if they exist
        if self.micropython_dir.exists():
            esp32_port_dir = self.micropython_dir / "ports" / "esp32"
            if esp32_port_dir.exists():
                # Find and remove build-* directories
                for build_dir in esp32_port_dir.glob("build-*"):
                    print(f"  Removing: {build_dir}")
                    shutil.rmtree(build_dir)
                    print(f"  [OK] Removed {build_dir}")

    def clean_python_cache(self) -> None:
        """Clean Python cache files."""
        print("Cleaning Python cache files...")

        cache_patterns = [
            "**/__pycache__",
            "**/*.pyc",
            "**/*.pyo",
            "**/*.pyd",
        ]

        for pattern in cache_patterns:
            for path in self.root_dir.glob(pattern):
                # Skip firmware/micropython directory
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
        """Clean MicroPython source (complete removal)."""
        if not self.micropython_dir.exists():
            print("MicroPython directory does not exist, nothing to clean")
            return

        print(f"Removing MicroPython directory: {self.micropython_dir}")
        try:
            shutil.rmtree(self.micropython_dir)
            print("[OK] MicroPython directory removed")
        except Exception as e:
            print(f"[ERROR] Failed to remove MicroPython: {e}")

    def clean(self) -> bool:
        """Execute the cleaning process."""
        print("=" * 60)
        print("StripAlerts ESP32 Build Cleaner")
        print("=" * 60)

        self.clean_build_artifacts()
        self.clean_python_cache()

        if self.all_clean:
            print("\nPerforming deep clean (including MicroPython)...")
            self.clean_micropython()

        print("\n" + "=" * 60)
        print("[SUCCESS] Cleaning completed successfully")
        print("=" * 60)

        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean StripAlerts ESP32 build artifacts"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Clean everything including MicroPython source",
    )

    args = parser.parse_args()

    # Get the project root directory
    root_dir = Path(__file__).parent.parent.resolve()

    # Create and run the cleaner
    cleaner = BuildCleaner(root_dir=root_dir, all_clean=args.all)

    success = cleaner.clean()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
