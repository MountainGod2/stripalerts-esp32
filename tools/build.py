"""
Build script for StripAlerts firmware.
Compiles MicroPython with frozen modules.
Includes error handling, dependency checking, and filesystem validation.
"""

import os
import subprocess
import sys
from pathlib import Path
import shutil
import time


class BuildError(Exception):
    """Custom exception for build errors."""
    pass


def check_dependencies():
    """Check if required build tools are available."""
    print("\n" + "=" * 60)
    print("Checking dependencies...")
    print("=" * 60)

    required_tools = {
        "git": "git",
        "make": "make",
        "python3": "python3",
        "esptool.py": "esptool.py",
    }

    missing = []
    for name, command in required_tools.items():
        try:
            subprocess.run(
                [command, "--version"] if command != "esptool.py" else [command, "version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            print(f"[OK] {name}")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            print(f"[FAIL] {name} - NOT FOUND")
            missing.append(name)

    if missing:
        print(f"\nError: Missing required tools: {', '.join(missing)}")
        print("\nInstall with:")
        if "esptool.py" in missing:
            print("  pip install esptool")
        if "make" in missing or "git" in missing:
            print("  sudo apt-get install build-essential git")
        raise BuildError("Missing dependencies")

    print("[OK] All dependencies found")


def check_compiler():
    """Check for ARM cross-compiler."""
    print("\nChecking ESP32 cross-compiler...")
    compilers = [
        "xtensa-esp32-elf-gcc",
        "xtensa-esp32s3-elf-gcc",
    ]

    found = False
    for compiler in compilers:
        try:
            subprocess.run(
                [compiler, "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            print(f"[OK] Found {compiler}")
            found = True
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    if not found:
        print("[FAIL] ESP32 cross-compiler not found")
        print("\nInstall from: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/")
        print("Or use: pip install esp-idf")
        raise BuildError("Cross-compiler not found")


def check_micropython_source(micropython_dir):
    """Check if MicroPython source exists, clone if needed."""
    print("\n" + "=" * 60)
    print("Checking MicroPython source...")
    print("=" * 60)

    if micropython_dir.exists():
        print(f"[OK] MicroPython source found at {micropython_dir}")
        return

    print(f"[FAIL] MicroPython source not found at {micropython_dir}")
    print("\nCloning MicroPython...")

    try:
        micropython_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/micropython/micropython.git",
                str(micropython_dir),
            ],
            check=True,
            timeout=300,
        )
        print(f"[OK] Cloned MicroPython to {micropython_dir}")
    except subprocess.CalledProcessError as e:
        raise BuildError(f"Failed to clone MicroPython: {e}")
    except subprocess.TimeoutExpired:
        raise BuildError("Cloning MicroPython timed out")


def setup_frozen_modules(frozen_dir, esp32_dir):
    """Setup frozen modules configuration."""
    print("\n" + "=" * 60)
    print("Setting up frozen modules...")
    print("=" * 60)

    if not frozen_dir.exists():
        print(f"[WARN] Frozen modules directory not found: {frozen_dir}")
        print("Building without frozen modules")
        return False

    # Create manifest if it doesn't exist
    manifest_src = frozen_dir / "manifest.py"
    if not manifest_src.exists():
        print(f"[WARN] Manifest not found at {manifest_src}")
        print("Creating basic manifest...")
        manifest_src.parent.mkdir(parents=True, exist_ok=True)
        manifest_src.write_text(
            "# Frozen modules manifest\n"
            "# Add modules here for freezing\n"
        )

    print(f"[OK] Frozen modules directory: {frozen_dir}")
    print(f"[OK] Manifest found: {manifest_src}")
    return True


def build_mpy_cross(micropython_dir):
    """Build mpy-cross tool."""
    print("\n" + "=" * 60)
    print("Building mpy-cross...")
    print("=" * 60)

    mpy_cross_dir = micropython_dir / "mpy-cross"

    if not mpy_cross_dir.exists():
        raise BuildError(f"mpy-cross directory not found: {mpy_cross_dir}")

    try:
        subprocess.run(
            ["make", "-j4"],
            cwd=mpy_cross_dir,
            check=True,
            timeout=300,
        )
        print("[OK] mpy-cross built successfully")
    except subprocess.CalledProcessError as e:
        raise BuildError(f"mpy-cross build failed: {e}")
    except subprocess.TimeoutExpired:
        raise BuildError("mpy-cross build timed out")


def build_esp32_firmware(micropython_dir, frozen_dir, board, build_dir):
    """Build ESP32 firmware."""
    print("\n" + "=" * 60)
    print(f"Building ESP32 firmware ({board})...")
    print("=" * 60)

    esp32_dir = micropython_dir / "ports" / "esp32"

    if not esp32_dir.exists():
        raise BuildError(f"ESP32 port not found: {esp32_dir}")

    # Setup environment
    env = os.environ.copy()

    # Add frozen modules if available
    manifest_src = frozen_dir / "manifest.py"
    if manifest_src.exists():
        env["FROZEN_MANIFEST"] = str(manifest_src)
        print(f"Using frozen modules from: {manifest_src}")

    # Build submodules
    print("\n1. Updating submodules...")
    try:
        subprocess.run(
            ["make", "submodules"],
            cwd=esp32_dir,
            env=env,
            check=True,
            timeout=300,
        )
        print("[OK] Submodules updated")
    except subprocess.CalledProcessError as e:
        raise BuildError(f"Submodule update failed: {e}")
    except subprocess.TimeoutExpired:
        raise BuildError("Submodule update timed out")

    # Build firmware
    print(f"\n2. Building firmware for {board}...")
    try:
        subprocess.run(
            ["make", f"BOARD={board}", "-j4"],
            cwd=esp32_dir,
            env=env,
            check=True,
            timeout=600,
        )
        print("[OK] Firmware build completed")
    except subprocess.CalledProcessError as e:
        raise BuildError(f"Firmware build failed: {e}")
    except subprocess.TimeoutExpired:
        raise BuildError("Firmware build timed out")

    # Locate and copy built firmware
    built_firmware = esp32_dir / f"build-{board}" / "firmware.bin"

    if not built_firmware.exists():
        # Try alternate paths
        alt_paths = [
            esp32_dir / f"build-{board}" / "combined.bin",
            esp32_dir / "build" / "firmware.bin",
            esp32_dir / "build" / "combined.bin",
        ]

        for alt_path in alt_paths:
            if alt_path.exists():
                built_firmware = alt_path
                break

    if not built_firmware.exists():
        raise BuildError(
            f"Firmware not found at {built_firmware} or alternate paths"
        )

    build_dir.mkdir(parents=True, exist_ok=True)
    output_firmware = build_dir / "firmware.bin"
    shutil.copy(built_firmware, output_firmware)

    print(f"[OK] Firmware copied to: {output_firmware}")
    print(f"  Size: {output_firmware.stat().st_size} bytes")

    return output_firmware


def verify_firmware_file(firmware_path):
    """Verify firmware file exists and is valid."""
    print("\n" + "=" * 60)
    print("Verifying firmware...")
    print("=" * 60)

    if not firmware_path.exists():
        raise BuildError(f"Firmware file not found: {firmware_path}")

    size = firmware_path.stat().st_size
    if size < 100000:  # Firmware should be at least ~100KB
        raise BuildError(f"Firmware file seems too small ({size} bytes)")

    print(f"[OK] Firmware file valid: {firmware_path}")
    print(f"  Size: {size:,} bytes")


def flash_firmware(firmware_path, port, chip="esp32s3", baud=460800):
    """Flash firmware to device."""
    print("\n" + "=" * 60)
    print(f"Flashing firmware to {port}...")
    print("=" * 60)

    if not firmware_path.exists():
        raise BuildError(f"Firmware file not found: {firmware_path}")

    print(f"Chip: {chip}")
    print(f"Port: {port}")
    print(f"Baud: {baud}")

    try:
        subprocess.run(
            [
                "esptool.py",
                "--chip",
                chip,
                "--port",
                port,
                "--baud",
                str(baud),
                "erase_flash",
            ],
            check=True,
            timeout=120,
        )
        print("[OK] Flash erased")

        subprocess.run(
            [
                "esptool.py",
                "--chip",
                chip,
                "--port",
                port,
                "--baud",
                str(baud),
                "write_flash",
                "-z",
                "0x0",
                str(firmware_path),
            ],
            check=True,
            timeout=120,
        )
        print("[OK] Firmware flashed successfully")

    except subprocess.CalledProcessError as e:
        raise BuildError(f"Flashing failed: {e}")
    except subprocess.TimeoutExpired:
        raise BuildError("Flashing timed out")


def validate_filesystem(port="a0", timeout=30):
    """Validate that ESP32 filesystem is working."""
    print("\n" + "=" * 60)
    print("Validating filesystem...")
    print("=" * 60)

    print("Waiting for device to boot...")
    time.sleep(3)

    try:
        # Test basic connection
        result = subprocess.run(
            ["mpremote", port, "eval", "1+1"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            print("[FAIL] Device not responding")
            return False

        print("[OK] Device responding")

        # Test filesystem
        result = subprocess.run(
            ["mpremote", port, "exec", "import os; print(len(os.listdir('/')))"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            print("[FAIL] Filesystem not accessible")
            return False

        print("[OK] Filesystem accessible")

        # Test mkdir
        result = subprocess.run(
            ["mpremote", port, "exec", "import os; os.mkdir('/test'); os.rmdir('/test')"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            print("[FAIL] Filesystem is read-only or corrupted")
            return False

        print("[OK] Filesystem is read-write")
        return True

    except FileNotFoundError:
        print("[WARN] mpremote not found - skipping filesystem validation")
        return None
    except subprocess.TimeoutExpired:
        print("[WARN] Filesystem validation timed out")
        return None
    except Exception as e:
        print(f"[WARN] Filesystem validation error: {e}")
        return None


def build_firmware(flash_device=None, chip="esp32s3", port="/dev/ttyACM0"):
    """Build MicroPython firmware with frozen modules."""

    project_root = Path(__file__).parent.parent
    firmware_dir = project_root / "firmware"
    micropython_dir = firmware_dir / "micropython"
    build_dir = firmware_dir / "build"
    frozen_dir = project_root / "frozen"

    print("\n" + "=" * 60)
    print("StripAlerts Firmware Build")
    print("=" * 60)

    try:
        # Phase 1: Check environment
        check_dependencies()
        check_compiler()

        # Phase 2: Prepare sources
        check_micropython_source(micropython_dir)
        setup_frozen_modules(frozen_dir, firmware_dir / "micropython" / "ports" / "esp32")

        # Phase 3: Build
        build_mpy_cross(micropython_dir)
        firmware_path = build_esp32_firmware(
            micropython_dir, frozen_dir, chip, build_dir
        )

        # Phase 4: Verify
        verify_firmware_file(firmware_path)

        # Phase 5: Flash if requested
        if flash_device:
            flash_firmware(firmware_path, port, chip)
            validate_filesystem(flash_device)

        print("\n" + "=" * 60)
        print("[OK] BUILD SUCCESSFUL")
        print("=" * 60)
        print(f"\nFirmware: {firmware_path}")
        print(f"Size: {firmware_path.stat().st_size:,} bytes")

        if flash_device:
            print(f"\n[OK] Flashed to {port}")
            print("Device should be ready to use")
        else:
            print("\nTo flash, run:")
            print(f"  esptool.py --chip {chip} --port {port} write_flash -z 0x0 {firmware_path}")

        return 0

    except BuildError as e:
        print("\n[FAIL] BUILD FAILED")
        print(f"Error: {e}")
        print("=" * 60)
        return 1

    except Exception as e:
        print("\n[FAIL] UNEXPECTED ERROR")
        print(f"Error: {e}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build StripAlerts firmware")
    parser.add_argument(
        "--flash",
        action="store_true",
        help="Flash firmware to device after building",
    )
    parser.add_argument(
        "--port",
        default="/dev/ttyACM0",
        help="Serial port (default: /dev/ttyACM0)",
    )
    parser.add_argument(
        "--chip",
        default="esp32s3",
        help="Chip type (default: esp32s3)",
    )
    parser.add_argument(
        "--device",
        default="a0",
        help="mpremote device shortcut for validation (default: a0)",
    )

    args = parser.parse_args()

    flash_device = args.device if args.flash else None
    sys.exit(build_firmware(flash_device=flash_device, chip=args.chip, port=args.port))