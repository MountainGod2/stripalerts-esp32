"""
Upload script for StripAlerts runtime code.
Uploads src/ directory to ESP32 via serial or WebREPL.
"""

import sys
from pathlib import Path


def upload_files(port="/dev/ttyUSB0", method="ampy"):
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
    
    files_to_upload = [
        "boot.py",
        "main.py",
        "stripalerts/"
    ]
    
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
        "--port", port,
        "--buffer-size", "512",  # ESP32-S3 USB CDC can be sensitive to buffer size
        "rsync", str(src_dir) + "/", "/"
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to upload with rshell: {e}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Upload StripAlerts runtime code")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--method", default="ampy", choices=["ampy", "rshell"], help="Upload method")
    
    args = parser.parse_args()
    sys.exit(upload_files(args.port, args.method))
