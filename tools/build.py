"""
Build script for StripAlerts firmware.
Compiles MicroPython with frozen modules.
"""

import os
import subprocess
import sys
from pathlib import Path


def build_firmware():
    """Build MicroPython firmware with frozen modules."""

    project_root = Path(__file__).parent.parent
    firmware_dir = project_root / "firmware"
    micropython_dir = firmware_dir / "micropython"
    build_dir = firmware_dir / "build"
    frozen_dir = project_root / "frozen"

    print("=" * 60)
    print("StripAlerts Firmware Build")
    print("=" * 60)

    # Check if MicroPython source exists
    if not micropython_dir.exists():
        print("Error: MicroPython source not found!")
        print(f"Please clone MicroPython to: {micropython_dir}")
        print("\nRun:")
        print("  cd firmware")
        print("  git clone https://github.com/micropython/micropython.git")
        return 1

    # Ensure build directory exists
    build_dir.mkdir(parents=True, exist_ok=True)

    # Build steps
    print("\n1. Building mpy-cross...")
    mpy_cross_dir = micropython_dir / "mpy-cross"
    subprocess.run(["make"], cwd=mpy_cross_dir, check=True)

    print("\n2. Configuring ESP32 port...")
    esp32_dir = micropython_dir / "ports" / "esp32"

    # Copy manifest to ESP32 port
    manifest_src = frozen_dir / "manifest.py"
    manifest_dst = esp32_dir / "boards" / "manifest_stripalerts.py"
    if manifest_src.exists():
        import shutil

        shutil.copy(manifest_src, manifest_dst)
        print(f"Copied manifest to {manifest_dst}")

    print("\n3. Building ESP32 firmware...")
    env = os.environ.copy()
    env["FROZEN_MANIFEST"] = str(manifest_dst)
    env["FROZEN_DIR"] = str(frozen_dir)

    # Use ESP32_GENERIC_S3 board for ESP32-S3
    board = env.get("BOARD", "ESP32_GENERIC_S3")

    subprocess.run(["make", "submodules"], cwd=esp32_dir, env=env, check=True)

    subprocess.run(["make", f"BOARD={board}"], cwd=esp32_dir, env=env, check=True)

    # Copy built firmware
    built_firmware = esp32_dir / f"build-{board}" / "firmware.bin"
    if built_firmware.exists():
        import shutil

        shutil.copy(built_firmware, build_dir / "firmware.bin")
        print("\n✓ Firmware built successfully!")
        print(f"  Output: {build_dir / 'firmware.bin'}")
    else:
        print("\n✗ Build failed - firmware.bin not found")
        return 1

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(build_firmware())
