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
    import time
    import tempfile

    # Test connection first
    print("Testing connection...")
    try:
        result = subprocess.run(
            ["mpremote", "connect", port, "exec", "print('Connected')"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            print("Connection test failed:")
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

    # Try to create a simple test file to verify filesystem access
    print("Verifying filesystem access...")
    try:
        test_cmd = "with open('/.test', 'w') as f: f.write('test')"
        result = subprocess.run(
            ["mpremote", "connect", port, "exec", test_cmd],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # Clean up test file
            subprocess.run(
                ["mpremote", "connect", port, "exec", "import os; os.remove('/.test')"],
                capture_output=True,
                timeout=5
            )
            print("✓ Filesystem accessible")
        else:
            print("Warning: Filesystem test failed, but continuing...")
    except Exception as e:
        print(f"Warning: Filesystem test failed: {e}")

    # Note: Skipping soft reset as it can cause USB serial connection issues
    # The device will be reset after upload completes
    
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
                        # Create directory using exec command
                        mkdir_cmd = f"import os; os.mkdir('{remote_dir}')"
                        cmd = ["mpremote", "connect", port, "exec", mkdir_cmd]
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
                    
                    # Read file content
                    with open(local_file, 'rb') as f:
                        content = f.read()
                    
                    # Write file using exec command with binary data
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            chunk_size = 512
                            
                            # Create/truncate the file
                            create_cmd = f"f = open('{remote_file}', 'wb')"
                            result = subprocess.run(
                                ["mpremote", "connect", port, "exec", create_cmd],
                                capture_output=True, text=True, timeout=10
                            )
                            
                            if result.returncode != 0:
                                if attempt < max_retries - 1:
                                    print(f"    Retry {attempt + 1}/{max_retries}...")
                                    time.sleep(1)
                                    continue
                                print(f"    Error: {result.stderr.strip()}")
                                raise subprocess.CalledProcessError(result.returncode, ["mpremote"])
                            
                            # Write content in chunks
                            for i in range(0, len(content), chunk_size):
                                chunk = content[i:i+chunk_size]
                                byte_list = ','.join(str(b) for b in chunk)
                                write_cmd = f"f.write(bytes([{byte_list}]))"
                                result = subprocess.run(
                                    ["mpremote", "connect", port, "exec", write_cmd],
                                    capture_output=True, text=True, timeout=10
                                )
                                if result.returncode != 0:
                                    raise subprocess.CalledProcessError(result.returncode, ["mpremote"])
                            
                            # Close the file
                            close_cmd = "f.close()"
                            subprocess.run(
                                ["mpremote", "connect", port, "exec", close_cmd],
                                capture_output=True, timeout=5
                            )
                            break
                            
                        except subprocess.TimeoutExpired:
                            if attempt < max_retries - 1:
                                print(f"    Timeout, retry {attempt + 1}/{max_retries}...")
                                time.sleep(1)
                                continue
                            raise
                        except subprocess.CalledProcessError:
                            if attempt < max_retries - 1:
                                print(f"    Error, retry {attempt + 1}/{max_retries}...")
                                time.sleep(1)
                                continue
                            raise
                    
                    time.sleep(0.1)  # Small delay between files
        else:
            # For single files, write directly using exec command
            remote_file = f"/{item}"
            
            # Read file content
            with open(src_path, 'rb') as f:
                content = f.read()
            
            # Write file using exec command with binary data
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Write file in chunks to avoid command line length limits
                    chunk_size = 512
                    
                    # First, create/truncate the file
                    create_cmd = f"f = open('{remote_file}', 'wb')"
                    result = subprocess.run(
                        ["mpremote", "connect", port, "exec", create_cmd],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    if result.returncode != 0:
                        if attempt < max_retries - 1:
                            print(f"Retry {attempt + 1}/{max_retries}...")
                            time.sleep(1)
                            continue
                        print(f"Error creating file: {result.stderr.strip()}")
                        raise subprocess.CalledProcessError(result.returncode, ["mpremote"])
                    
                    # Write content in chunks
                    for i in range(0, len(content), chunk_size):
                        chunk = content[i:i+chunk_size]
                        # Convert bytes to list of integers
                        byte_list = ','.join(str(b) for b in chunk)
                        write_cmd = f"f.write(bytes([{byte_list}]))"
                        result = subprocess.run(
                            ["mpremote", "connect", port, "exec", write_cmd],
                            capture_output=True, text=True, timeout=10
                        )
                        if result.returncode != 0:
                            raise subprocess.CalledProcessError(result.returncode, ["mpremote"])
                    
                    # Close the file
                    close_cmd = "f.close()"
                    subprocess.run(
                        ["mpremote", "connect", port, "exec", close_cmd],
                        capture_output=True, timeout=5
                    )
                    
                    print(f"✓ Uploaded {item}")
                    break
                    
                except subprocess.TimeoutExpired:
                    if attempt < max_retries - 1:
                        print(f"Timeout, retry {attempt + 1}/{max_retries}...")
                        time.sleep(1)
                        continue
                    print(f"Failed to upload {item}")
                    raise
                except subprocess.CalledProcessError:
                    if attempt < max_retries - 1:
                        print(f"Error, retry {attempt + 1}/{max_retries}...")
                        time.sleep(1)
                        continue
                    print(f"Failed to upload {item}")
                    raise
            
            time.sleep(0.2)
    
    # Reset device after upload to run new code
    print("\nResetting device to run new code...")
    try:
        subprocess.run(
            ["mpremote", "connect", port, "soft-reset"],
            capture_output=True,
            timeout=5
        )
        print("✓ Device reset")
    except Exception as e:
        print(f"Warning: Failed to reset device: {e}")
        print("You may need to manually reset the device")
    
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
