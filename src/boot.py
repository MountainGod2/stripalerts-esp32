"""
StripAlerts Boot Configuration
Initializes filesystem and prepares system on first boot.
"""

import os
import esp


def initialize_filesystem():
    """Initialize filesystem if not already present."""
    try:
        # Check if filesystem is accessible
        os.listdir("/")
        print("[BOOT] Filesystem accessible")
        return True
    except OSError:
        print("[BOOT] Initializing filesystem...")
        try:
            # Try to mount/initialize VFS
            import esp32

            # For ESP32, the filesystem is typically available by default
            # but we may need to format it on first boot
            print("[BOOT] Attempting filesystem format...")

            # Try creating a test directory to verify write access
            try:
                os.mkdir("/lib")
                print("[BOOT] Filesystem writable")
                return True
            except OSError as e:
                if "EEXIST" in str(e):
                    print("[BOOT] Filesystem already initialized")
                    return True
                print(f"[BOOT] Warning: Filesystem may be read-only: {e}")
                return False

        except Exception as e:
            print(f"[BOOT] Filesystem initialization failed: {e}")
            return False


def setup_paths():
    """Setup import paths for application modules."""
    try:
        # Add src to path if it exists
        if "/src" not in os.listdir("/"):
            os.mkdir("/src")

        import sys

        if "/src" not in sys.path:
            sys.path.append("/src")
            print("[BOOT] Added /src to path")

    except Exception as e:
        print(f"[BOOT] Path setup warning: {e}")


def main():
    """Main boot sequence."""
    print("\n" + "=" * 50)
    print("StripAlerts ESP32 Boot")
    print("=" * 50)

    # Initialize filesystem
    fs_ok = initialize_filesystem()
    if not fs_ok:
        print("[BOOT] Warning: Filesystem may not be fully functional")

    # Setup paths
    setup_paths()

    # Show available space
    try:
        stat = os.statvfs("/")
        total = stat[0] * stat[2]
        free = stat[0] * stat[3]
        used = total - free
        print(f"[BOOT] Filesystem: {used}/{total} bytes used ({free} bytes free)")
    except Exception as e:
        print(f"[BOOT] Could not get filesystem stats: {e}")

    print("[BOOT] Boot sequence complete")
    print("=" * 50 + "\n")


# Run boot sequence
if __name__ == "__main__":
    main()
