#!/usr/bin/env python3
"""
Deploy script for StripAlerts ESP32 firmware.

This script combines build, upload, and monitor operations for a complete
deployment workflow.
"""

import argparse
import sys
from pathlib import Path

from tools.build import FirmwareBuilder
from tools.upload import FirmwareUploader
from tools.monitor import SerialMonitor


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Deploy StripAlerts ESP32 firmware (build + upload + monitor)"
    )
    parser.add_argument(
        "--port", "-p", help="Serial port (auto-detected if not specified)"
    )
    parser.add_argument(
        "--board",
        default="ESP32_GENERIC_S3",
        help="ESP32 board variant (default: ESP32_GENERIC_S3)",
    )
    parser.add_argument(
        "--baud", type=int, default=460800, help="Upload baud rate (default: 460800)"
    )
    parser.add_argument("--clean", action="store_true", help="Clean before building")
    parser.add_argument(
        "--erase", action="store_true", help="Erase flash before uploading"
    )
    parser.add_argument("--skip-build", action="store_true", help="Skip build step")
    parser.add_argument("--skip-upload", action="store_true", help="Skip upload step")
    parser.add_argument("--skip-monitor", action="store_true", help="Skip monitor step")

    args = parser.parse_args()

    # Get the project root directory
    root_dir = Path(__file__).parent.parent.resolve()

    # Build phase
    if not args.skip_build:
        print("\n" + "=" * 60)
        print("STEP 1: Building Firmware")
        print("=" * 60 + "\n")

        builder = FirmwareBuilder(root_dir=root_dir, board=args.board, clean=args.clean)

        if not builder.build():
            print("\n[ERROR] Build failed")
            sys.exit(1)
    else:
        print("\nSkipping build step")

    # Upload phase
    if not args.skip_upload:
        print("\n" + "=" * 60)
        print("STEP 2: Uploading Firmware")
        print("=" * 60 + "\n")

        uploader = FirmwareUploader(
            root_dir=root_dir,
            port=args.port,
            baud=args.baud,
            board=args.board,
            erase=args.erase,
        )

        if not uploader.upload():
            print("\n[ERROR] Upload failed")
            sys.exit(1)
    else:
        print("\nSkipping upload step")

    # Monitor phase
    if not args.skip_monitor:
        print("\n" + "=" * 60)
        print("STEP 3: Monitoring Device")
        print("=" * 60 + "\n")

        monitor = SerialMonitor(
            port=args.port,
            baud=115200,  # Standard monitor baud
        )

        monitor.monitor()
    else:
        print("\nSkipping monitor step")

    print("\n" + "=" * 60)
    print("Deployment workflow completed successfully")
    print("=" * 60)


if __name__ == "__main__":
    main()
