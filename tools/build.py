#!/usr/bin/env python3
"""
Build script for StripAlerts ESP32 firmware.

This script builds a custom MicroPython firmware with frozen modules
for the ESP32 platform.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


class FirmwareBuilder:
    """Handles building of ESP32 MicroPython firmware with frozen modules."""

    def __init__(self, root_dir: Path, board: str = "ESP32_GENERIC", clean: bool = False):
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
        
    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        print("Checking prerequisites...")
        
        # Check for ESP-IDF environment
        esp_idf_path = os.environ.get("IDF_PATH")
        if not esp_idf_path:
            print("[WARNING] IDF_PATH environment variable not set")
            print("Please source ESP-IDF export.sh or export.bat first")
            return False
        
        print(f"[OK] ESP-IDF found at: {esp_idf_path}")
        
        # Check if idf.py is available
        try:
            result = subprocess.run(
                ["idf.py", "--version"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                print(f"[OK] idf.py version: {result.stdout.strip()}")
            else:
                print("[WARNING] idf.py not found in PATH")
                return False
        except FileNotFoundError:
            print("[WARNING] idf.py not found")
            return False
        
        return True
    
    def setup_micropython(self) -> bool:
        """Clone and setup MicroPython repository."""
        if self.micropython_dir.exists():
            print(f"[OK] MicroPython already cloned at {self.micropython_dir}")
            return True
        
        print("Cloning MicroPython repository...")
        try:
            subprocess.run(
                [
                    "git", "clone", "--depth", "1",
                    "https://github.com/micropython/micropython.git",
                    str(self.micropython_dir)
                ],
                check=True,
                cwd=str(self.firmware_dir)
            )
            print("[OK] MicroPython cloned successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to clone MicroPython: {e}")
            return False
    
    def build_mpy_cross(self) -> bool:
        """Build the mpy-cross compiler."""
        mpy_cross_dir = self.micropython_dir / "mpy-cross"
        
        print("Building mpy-cross compiler...")
        try:
            subprocess.run(
                ["make"],
                check=True,
                cwd=str(mpy_cross_dir)
            )
            print("[OK] mpy-cross built successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to build mpy-cross: {e}")
            return False
    
    def setup_frozen_manifest(self) -> bool:
        """Setup the manifest for frozen modules."""
        print("Setting up frozen module manifest...")
        
        # Create a custom manifest that includes board defaults and frozen modules
        manifest_path = self.esp32_port_dir / "boards" / "manifest_stripalerts.py"
        
        # Verify frozen directory exists
        if not self.frozen_dir.exists():
            print(f"Warning: Frozen directory not found at {self.frozen_dir}")
            return False
        
        # Create manifest following MicroPython best practices
        manifest_content = f'''"""
Custom manifest for StripAlerts firmware.
Freezes the StripAlerts application into the firmware.
"""
# Include base board manifest (which includes port manifest)
# Try board-specific manifest first, fall back to generic port manifest
try:
    include("$(PORT_DIR)/boards/{self.board}/manifest.py")
except:
    include("$(PORT_DIR)/boards/manifest.py")

# Freeze StripAlerts package using recommended package() function
package("stripalerts", base_path="{str(self.frozen_dir.resolve())}", opt=3)
'''
        
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(manifest_content)
        print(f"[OK] Frozen manifest created at {manifest_path}")
        
        return True
    
    def clean_build(self) -> None:
        """Clean the build directory."""
        build_dir = self.esp32_port_dir / "build-" / self.board
        if build_dir.exists():
            print(f"Cleaning build directory: {build_dir}")
            shutil.rmtree(build_dir)
            print("[OK] Build directory cleaned")
    
    def build_firmware(self) -> bool:
        """Build the ESP32 firmware."""
        print(f"Building firmware for {self.board}...")
        
        if self.clean:
            self.clean_build()
        
        # Set environment variables for the build
        env = os.environ.copy()
        env["FROZEN_MANIFEST"] = str(
            self.esp32_port_dir / "boards" / "manifest_stripalerts.py"
        )
        
        try:
            # Build the firmware using make
            subprocess.run(
                ["make", "BOARD=" + self.board, "submodules"],
                check=True,
                cwd=str(self.esp32_port_dir),
                env=env
            )
            
            subprocess.run(
                ["make", "BOARD=" + self.board],
                check=True,
                cwd=str(self.esp32_port_dir),
                env=env
            )
            
            print("[OK] Firmware built successfully")
            
            # Copy firmware to build directory
            self.copy_firmware_artifacts()
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to build firmware: {e}")
            return False
    
    def copy_firmware_artifacts(self) -> None:
        """Copy built firmware to the project build directory."""
        build_dir = self.root_dir / "firmware" / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        
        board_build_dir = self.esp32_port_dir / "build-" / self.board
        
        # Find and copy firmware files
        firmware_files = [
            "firmware.bin",
            "bootloader/bootloader.bin",
            "partition_table/partition-table.bin",
        ]
        
        for firmware_file in firmware_files:
            src = board_build_dir / firmware_file
            if src.exists():
                dest = build_dir / src.name
                shutil.copy2(src, dest)
                print(f"[OK] Copied {src.name} to {build_dir}")
        
        # Also copy the complete firmware.bin to a versioned name
        firmware_bin = board_build_dir / "firmware.bin"
        if firmware_bin.exists():
            # Get version from pyproject.toml if available
            version = "dev"
            pyproject_path = self.root_dir / "pyproject.toml"
            if pyproject_path.exists():
                import re
                content = pyproject_path.read_text()
                match = re.search(r'version\s*=\s*"([^"]+)"', content)
                if match:
                    version = match.group(1)
            
            versioned_name = f"stripalerts-{version}-{self.board}.bin"
            dest = build_dir / versioned_name
            shutil.copy2(firmware_bin, dest)
            print(f"[OK] Created versioned firmware: {versioned_name}")
    
    def build(self) -> bool:
        """Execute the complete build process."""
        print("=" * 60)
        print("StripAlerts ESP32 Firmware Builder")
        print("=" * 60)
        
        if not self.check_prerequisites():
            print("\n[ERROR] Prerequisites check failed")
            return False
        
        if not self.setup_micropython():
            return False
        
        if not self.build_mpy_cross():
            return False
        
        if not self.setup_frozen_manifest():
            return False
        
        if not self.build_firmware():
            return False
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Build completed successfully")
        print("=" * 60)
        print(f"\nFirmware files are in: {self.root_dir / 'firmware' / 'build'}")
        
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build StripAlerts ESP32 firmware"
    )
    parser.add_argument(
        "--board",
        default="ESP32_GENERIC",
        help="ESP32 board variant (default: ESP32_GENERIC)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean before building"
    )
    
    args = parser.parse_args()
    
    # Get the project root directory
    root_dir = Path(__file__).parent.parent.resolve()
    
    # Create and run the builder
    builder = FirmwareBuilder(
        root_dir=root_dir,
        board=args.board,
        clean=args.clean
    )
    
    success = builder.build()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
