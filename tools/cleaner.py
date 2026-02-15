"""Build cleaner for StripAlerts ESP32."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from utils import print_header, print_success, run_command

if TYPE_CHECKING:
    from pathlib import Path


class BuildCleaner:
    """Cleans build artifacts and caches."""

    def __init__(self, root_dir: Path, *, all_clean: bool = False) -> None:
        """Initialize build cleaner for project artifacts."""
        self.root_dir = root_dir
        self.all_clean = all_clean
        self.dist_dir = root_dir / "dist"
        self.micropython_dir = root_dir / "micropython"

    def clean_build_artifacts(self) -> None:
        """Remove dist/ and build-* directories."""
        print("Cleaning build artifacts...")

        if self.dist_dir.exists():
            print(f"  Removing: {self.dist_dir}")
            try:
                shutil.rmtree(self.dist_dir)
                print("  [OK] Removed dist directory")
            except Exception as e:
                print(f"  [ERROR] Failed to remove {self.dist_dir}: {e}")

        if self.micropython_dir.exists():
            esp32_port_dir = self.micropython_dir / "ports" / "esp32"
            if esp32_port_dir.exists():
                dirs_to_clean = list(esp32_port_dir.glob("build-*"))
                if (esp32_port_dir / "build").exists():
                    dirs_to_clean.append(esp32_port_dir / "build")

                for build_dir in dirs_to_clean:
                    if build_dir.is_dir():
                        print(f"  Removing: {build_dir.name}")
                        try:
                            shutil.rmtree(build_dir)
                        except Exception as e:
                            print(f"  [WARNING] Failed to remove {build_dir.name}: {e}")

    def clean_python_cache(self) -> None:
        """Remove __pycache__ and *.pyc files."""
        print("Cleaning Python cache files...")

        for pattern in ["**/__pycache__", "**/*.pyc", "**/*.pyo", "**/*.pyd"]:
            for path in self.root_dir.glob(pattern):
                if "micropython" in str(path):
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
        """Run 'make clean' in mpy-cross and esp32 port directories."""
        if not self.micropython_dir.exists():
            return

        print(f"Cleaning MicroPython artifacts in: {self.micropython_dir}")

        mpy_cross_dir = self.micropython_dir / "mpy-cross"
        if (mpy_cross_dir / "Makefile").exists():
            try:
                print("  Cleaning mpy-cross...")
                run_command(
                    ["make", "clean"],
                    cwd=mpy_cross_dir,
                )
                print("  [OK] Cleaned mpy-cross")
            except subprocess.CalledProcessError as e:
                print(f"  [WARNING] Failed to clean mpy-cross: {e}")

        esp32_dir = self.micropython_dir / "ports" / "esp32"
        if (esp32_dir / "Makefile").exists():
            if shutil.which("idf.py") is None:
                print("  [INFO] idf.py not found, artifacts removed manually.")
            else:
                try:
                    print("  Cleaning esp32 port...")
                    run_command(
                        ["make", "clean"],
                        cwd=esp32_dir,
                    )
                    print("  [OK] Cleaned esp32 port")
                except subprocess.CalledProcessError as e:
                    print(f"  [WARNING] Failed to clean esp32 port: {e}")

    def clean(self) -> bool:
        """Execute full cleaning workflow."""
        print_header("StripAlerts ESP32 Build Cleaner")

        self.clean_build_artifacts()
        self.clean_python_cache()

        if self.all_clean:
            print("\nPerforming deep clean (including MicroPython)...")
            self.clean_micropython()

        print_success("Clean completed")
        return True
