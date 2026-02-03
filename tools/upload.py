"""
Upload runtime code to ESP32.
Handles file transfers and validates successful upload.
"""

import argparse
import subprocess
import sys
from pathlib import Path


class UploadError(Exception):
    """Custom exception for upload errors."""
    pass


def validate_device(device):
    """Check if device is connected and responsive."""
    print(f"Validating device connection ({device})...")
    try:
        result = subprocess.run(
            ["mpremote", device, "eval", "1+1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise UploadError(f"Device not responding: {result.stderr}")
        print("[OK] Device connected and responsive")
        return True
    except FileNotFoundError:
        raise UploadError("mpremote not found. Install with: pip install mpremote")
    except subprocess.TimeoutExpired:
        raise UploadError("Device connection timed out")


def check_filesystem(device):
    """Check if device filesystem is writable."""
    print("Checking device filesystem...")
    try:
        result = subprocess.run(
            ["mpremote", device, "exec", "import os; os.listdir('/')"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise UploadError("Filesystem not accessible")
        print("[OK] Filesystem accessible")
        return True
    except subprocess.TimeoutExpired:
        raise UploadError("Filesystem check timed out")


def upload_directory(src_dir, dst_dir, device, exclude=None):
    """Upload a directory to device."""
    if exclude is None:
        exclude = {".pyc", "__pycache__", ".git"}

    src_path = Path(src_dir)
    if not src_path.exists():
        raise UploadError(f"Source directory not found: {src_dir}")

    print(f"Uploading {src_path.name}/ to {dst_dir}/...")

    # Create destination directory if it doesn't exist
    try:
        subprocess.run(
            ["mpremote", device, "fs", "mkdir", dst_dir],
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        print(f"[WARN] Warning: mkdir timed out for {dst_dir}")

    file_count = 0
    error_count = 0

    for file_path in src_path.rglob("*"):
        # Skip excluded files/directories
        if any(exc in file_path.parts for exc in exclude):
            continue

        if file_path.is_dir():
            # Create directory on device
            rel_path = file_path.relative_to(src_path)
            dst_path = f"{dst_dir}/{rel_path}".replace("\\", "/")
            try:
                subprocess.run(
                    ["mpremote", device, "fs", "mkdir", dst_path],
                    capture_output=True,
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                print(f"[WARN] Warning: mkdir timed out for {dst_path}")

        elif file_path.is_file():
            # Copy file to device
            rel_path = file_path.relative_to(src_path)
            dst_path = f"{dst_dir}/{rel_path}".replace("\\", "/")

            try:
                result = subprocess.run(
                    ["mpremote", device, "cp", str(file_path), f":{dst_path}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    file_count += 1
                    print(f"  [OK] {rel_path}")
                else:
                    error_count += 1
                    print(f"  [FAIL] {rel_path}: {result.stderr.strip()}")

            except subprocess.TimeoutExpired:
                error_count += 1
                print(f"  [FAIL] {rel_path}: timeout")

    print(f"Uploaded {file_count} file(s), {error_count} error(s)")
    return error_count == 0


def upload_runtime(device):
    """Upload runtime code to device."""
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"

    if not src_dir.exists():
        print(f"[WARN] Warning: {src_dir} not found, skipping runtime upload")
        return True

    print("\n" + "=" * 60)
    print("Uploading runtime code...")
    print("=" * 60)

    try:
        success = upload_directory(src_dir, "/src", device)
        if not success:
            print("[WARN] Some files failed to upload")
        print("[OK] Runtime upload complete")
        return success
    except UploadError as e:
        print(f"[FAIL] Upload failed: {e}")
        return False


def upload_frozen_modules(device):
    """Upload frozen modules if not built-in."""
    project_root = Path(__file__).parent.parent
    frozen_dir = project_root / "frozen"

    if not frozen_dir.exists():
        return True

    # Check if modules are already frozen (built into firmware)
    print("\nNote: Frozen modules are typically built into the firmware.")
    print("Only upload here if needed at runtime.")

    lib_dir = frozen_dir / "lib"
    if lib_dir.exists():
        print("\n" + "=" * 60)
        print("Uploading additional libraries...")
        print("=" * 60)

        try:
            success = upload_directory(lib_dir, "/lib", device)
            print("[OK] Library upload complete")
            return success
        except UploadError as e:
            print(f"[FAIL] Library upload failed: {e}")
            return False

    return True


def verify_upload(device):
    """Verify uploaded files are present."""
    print("\n" + "=" * 60)
    print("Verifying upload...")
    print("=" * 60)

    try:
        result = subprocess.run(
            ["mpremote", device, "fs", "ls", "/src"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            file_count = len([line for line in lines if line.strip()])
            print(f"[OK] Found {file_count} file(s) in /src")
            return True
        else:
            print("[WARN] Could not verify upload")
            return False

    except subprocess.TimeoutExpired:
        print("[WARN] Verification timed out")
        return False


def main():
    parser = argparse.ArgumentParser(description="Upload code to ESP32")
    parser.add_argument(
        "--port",
        default="/dev/ttyACM0",
        help="Serial port (default: /dev/ttyACM0)",
    )
    parser.add_argument(
        "--device",
        default="a0",
        help="mpremote device shortcut (default: a0)",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip verification step",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("StripAlerts Upload Tool")
    print("=" * 60)

    try:
        # Validate connection
        validate_device(args.device)

        # Check filesystem
        check_filesystem(args.device)

        # Upload runtime code
        if not upload_runtime(args.device):
            raise UploadError("Runtime upload failed")

        # Upload frozen modules
        if not upload_frozen_modules(args.device):
            print("[WARN] Library upload had errors")

        # Verify
        if not args.skip_verify:
            verify_upload(args.device)

        print("\n" + "=" * 60)
        print("[OK] UPLOAD SUCCESSFUL")
        print("=" * 60)
        return 0

    except UploadError as e:
        print("\n[FAIL] UPLOAD FAILED")
        print(f"Error: {e}")
        print("=" * 60)
        return 1

    except Exception as e:
        print("\n[FAIL] UNEXPECTED ERROR")
        print(f"Error: {e}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())