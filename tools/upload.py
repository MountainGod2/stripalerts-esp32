"""
Upload script for StripAlerts runtime code.
Uploads src/ directory to ESP32 via serial or WebREPL.
"""

import sys
from pathlib import Path


def upload_files(port="/dev/ttyACM0", method="ampy"):
    """Upload runtime files to ESP32."""

    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"

    print("=" * 60)
    print("StripAlerts Runtime Upload")
    print("=" * 60)

    if not src_dir.exists():
        print(f"Error: Source directory not found: {src_dir}")
        return 1

    print(f"\nUploading from: {src_dir}")
    print(f"Port: {port}")
    print(f"Method: {method}")

    if method == "ampy":
        upload_with_ampy(src_dir, port)
    elif method == "rshell":
        upload_with_rshell(src_dir, port)
    elif method == "mpremote":
        upload_with_mpremote(src_dir, port)
    else:
        print(f"Unknown upload method: {method}")
        return 1

    print("\n✓ Upload complete!")
    print("=" * 60)
    return 0


def upload_with_ampy(src_dir, port):
    """Upload using ampy (adafruit-ampy)."""
    import subprocess
    import time

    files_to_upload = ["boot.py", "main.py", "stripalerts/"]

    for item in files_to_upload:
        src_path = src_dir / item
        if not src_path.exists():
            print(f"Skipping {item} (not found)")
            continue

        print(f"Uploading {item}...")

        if src_path.is_dir():
            cmd = ["ampy", "--port", port, "put", str(src_path), item]
        else:
            cmd = ["ampy", "--port", port, "put", str(src_path)]

        try:
            subprocess.run(cmd, check=True)
            # Small delay for ESP32-S3 USB CDC to stabilize between uploads
            time.sleep(0.2)
        except subprocess.CalledProcessError as e:
            print(f"Failed to upload {item}: {e}")
            print("Note: If using ESP32-S3 USB CDC, try --method rshell instead")


def upload_with_rshell(src_dir, port):
    """Upload using rshell."""
    import subprocess

    # ESP32 uses / as root, not /pyboard/ (which is PyBoard-specific)
    cmd = [
        "rshell",
        "--port",
        port,
        "--buffer-size",
        "512",  # ESP32-S3 USB CDC can be sensitive to buffer size
        "rsync",
        str(src_dir) + "/",
        "/",
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to upload with rshell: {e}")
        raise


def upload_with_mpremote(src_dir, port):
    """Upload using mpremote (official MicroPython tool)."""
    import subprocess
    import os

    # Test connection first
    print("Testing connection...")
    try:
        result = subprocess.run(
            ["mpremote", "connect", port, "exec", "print('Connected')"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print(f"Connection test failed:")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            print("\nTroubleshooting tips:")
            print("1. Check if device is connected: ls -l /dev/ttyACM*")
            print("2. Reset the ESP32 (press RESET button)")
            print("3. Check permissions: sudo usermod -a -G dialout $USER")
            print("4. Try a different upload method: make upload UPLOAD_METHOD=ampy")
            return 1
        print("✓ Connection successful")
    except subprocess.TimeoutExpired:
        print("Connection timeout - device not responding")
        print("Try resetting the ESP32 and running again")
        return 1
    except FileNotFoundError:
        print("Error: mpremote not found. Install with: uv sync")
        return 1

    files_to_upload = ["boot.py", "main.py", "stripalerts/"]

    for item in files_to_upload:
        src_path = src_dir / item
        if not src_path.exists():
            print(f"Skipping {item} (not found)")
            continue

        print(f"Uploading {item}...")

        if src_path.is_dir():
            # For directories, upload all files recursively
            for root, dirs, files in os.walk(src_path):
                root_path = Path(root)
                rel_dir = root_path.relative_to(src_dir)
                
                # Create directory on device
                remote_dir = f"/{rel_dir}".replace("\\", "/")
                if remote_dir != "/":
                    try:
                        cmd = ["mpremote", "connect", port, "mkdir", remote_dir]
                        subprocess.run(cmd, check=False, capture_output=True)  # Ignore if exists
                    except subprocess.CalledProcessError:
                        pass
                
                # Upload files in this directory
                for file in files:
                    if file.endswith('.pyc') or file == '__pycache__':
                        continue
                    local_file = root_path / file
                    remote_file = f"{remote_dir}/{file}".replace("\\", "/")
                    print(f"  {remote_file}")
                    try:
                        cmd = ["mpremote", "connect", port, "cp", str(local_file), f":{remote_file}"]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"    Error: {result.stderr}")
                            raise subprocess.CalledProcessError(result.returncode, cmd)
                    except subprocess.CalledProcessError as e:
                        print(f"  Failed to upload {local_file}")
                        raise
        else:
            # For single files
            remote_file = f":/{item}"
            try:
                cmd = ["mpremote", "connect", port, "cp", str(src_path), remote_file]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Error: {result.stderr}")
                    raise subprocess.CalledProcessError(result.returncode, cmd)
            except subprocess.CalledProcessError as e:
                print(f"Failed to upload {item}")
                raise
    
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload StripAlerts runtime code")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port")
    parser.add_argument(
        "--method", default="ampy", choices=["ampy", "rshell", "mpremote"], help="Upload method"
    )

    args = parser.parse_args()
    sys.exit(upload_files(args.port, args.method))
