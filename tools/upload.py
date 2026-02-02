"""
Upload script for StripAlerts runtime code.
Uploads src/ directory to ESP32 via serial using mpremote.
"""

import sys
import subprocess
from pathlib import Path
from typing import List, Tuple


def get_files_to_upload(src_dir: Path) -> List[Tuple[Path, str]]:
    """
    Get list of files/directories to upload.

    Returns list of (source_path, target_name) tuples.
    """
    files = [
        (src_dir / "boot.py", "boot.py"),
        (src_dir / "main.py", "main.py"),
        (src_dir / "stripalerts", "stripalerts"),
    ]

    # Filter out non-existent paths
    return [(src, target) for src, target in files if src.exists()]


def upload_with_mpremote(src_dir: Path, port: str, clean: bool = False) -> None:
    """
    Upload using mpremote in a single connection.

    Args:
        src_dir: Source directory containing files to upload
        port: Serial port path (or "auto" for auto-detection)
        clean: Remove target directories before upload

    Raises:
        subprocess.CalledProcessError: If upload fails
    """
    files_to_upload = get_files_to_upload(src_dir)

    if not files_to_upload:
        print("Warning: No files found to upload")
        return

    # Base connect command
    connect_cmd = ["mpremote", "connect", port]

    # Build chained mpremote commands
    cmd = connect_cmd.copy()

    for src_path, target_name in files_to_upload:
        print(f"Preparing upload: {target_name}")

        if clean and src_path.is_dir():
            # Remove existing directory on device (ignore failure)
            cmd += ["fs", "rm", "-r", f":{target_name}"]

        if src_path.is_dir():
            cmd += ["cp", "-r", str(src_path), f":{target_name}"]
        else:
            cmd += ["cp", str(src_path), f":{target_name}"]

    try:
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True, timeout=120
        )

        if result.stdout:
            print(result.stdout)

        if result.stderr:
            # mpremote often logs info to stderr
            print(result.stderr)

    except subprocess.TimeoutExpired:
        print("Upload timed out")
        print("Try unplugging and reconnecting the device")
        raise
    except subprocess.CalledProcessError as e:
        print("Upload failed")
        if e.stderr:
            print(f"Error: {e.stderr}")
        print("\nTroubleshooting:")
        print("- Check device is connected and port is correct")
        print("- Try resetting the device")
        print("- Use --port auto for automatic port detection")
        print("- Verify mpremote is installed: pip install mpremote")
        raise


def soft_reset_device(port: str) -> None:
    """
    Perform a soft reset on the device after upload.

    Args:
        port: Serial port path (or "auto" for auto-detection)
    """
    print("\nPerforming soft reset...")

    cmd = ["mpremote", "connect", port, "soft-reset"]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=10)
        print("Device reset successfully")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print("Warning: Soft reset failed (usually not critical)")
        if hasattr(e, "stderr") and e.stderr:
            print(f"Error: {e.stderr}")


def upload_files(port: str = "auto", reset: bool = True, clean: bool = False) -> int:
    """
    Upload runtime files to ESP32.

    Args:
        port: Serial port path or "auto" for auto-detection
        reset: Whether to soft reset the device after upload
        clean: Remove target directories before upload

    Returns:
        0 on success, 1 on failure
    """
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"

    print("=" * 60)
    print("StripAlerts Runtime Upload")
    print("=" * 60)

    if not src_dir.is_dir():
        print(f"Error: Source directory not found or invalid: {src_dir}")
        return 1

    print(f"\nSource directory: {src_dir}")
    print(f"Serial port: {port}")
    print("Using: mpremote")
    if clean:
        print("Clean upload: enabled")
    print()

    try:
        upload_with_mpremote(src_dir, port, clean)

        if reset:
            soft_reset_device(port)

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("\nUpload failed!")
        print("=" * 60)
        return 1
    except KeyboardInterrupt:
        print("\nUpload cancelled by user")
        print("=" * 60)
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("=" * 60)
        return 1

    print("\nUpload complete!")
    print("=" * 60)
    return 0


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Upload StripAlerts runtime code to ESP32 using mpremote",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Auto-detect port
  %(prog)s --port /dev/ttyUSB0      # Specific port
  %(prog)s --port COM3              # Windows port
  %(prog)s --no-reset               # Skip soft reset
  %(prog)s --clean                  # Remove existing directories first
        """,
    )

    parser.add_argument(
        "--port", default="auto", help="Serial port (default: auto-detect)"
    )
    parser.add_argument(
        "--no-reset",
        dest="reset",
        action="store_false",
        help="Skip soft reset after upload",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove target directories before upload",
    )

    args = parser.parse_args()
    return upload_files(args.port, args.reset, args.clean)


if __name__ == "__main__":
    sys.exit(main())
