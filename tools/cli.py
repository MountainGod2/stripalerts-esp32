#!/usr/bin/env python3
"""StripAlerts ESP32 Development CLI.

Consolidated tool for building, uploading, monitoring, and managing
the StripAlerts ESP32 firmware and application files.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

from builder import FirmwareBuilder
from cleaner import BuildCleaner
from monitor import SerialMonitor
from uploader import FileUploader, FirmwareUploader
from utils import print_header, print_success


# Command handlers
def cmd_build(args) -> int:
    """Build command handler."""
    root_dir = Path(__file__).parent.parent.resolve()
    builder = FirmwareBuilder(root_dir, args.board, clean=args.clean)
    return 0 if builder.build() else 1


def cmd_flash(args) -> int:
    """Flash firmware command handler."""
    root_dir = Path(__file__).parent.parent.resolve()
    uploader = FirmwareUploader(
        root_dir, args.board, args.port, args.baud, erase=args.erase
    )
    return 0 if uploader.upload() else 1


def cmd_upload(args) -> int:
    """Upload application files command handler."""
    root_dir = Path(__file__).parent.parent.resolve()
    uploader = FileUploader(root_dir, args.port)
    return 0 if uploader.upload_files() else 1


def cmd_monitor(args) -> int:
    """Monitor command handler."""
    monitor = SerialMonitor(args.port, args.baud)
    return 0 if monitor.monitor() else 1


def cmd_clean(args) -> int:
    """Clean command handler."""
    root_dir = Path(__file__).parent.parent.resolve()
    cleaner = BuildCleaner(root_dir, all_clean=args.all)
    return 0 if cleaner.clean() else 1


def cmd_deploy(args) -> int:
    """Deploy command handler (build + flash + upload + monitor)."""
    root_dir = Path(__file__).parent.parent.resolve()

    # Step 1: Build
    if not args.skip_build:
        print_header("STEP 1: Building Firmware")
        builder = FirmwareBuilder(root_dir, args.board, clean=args.clean)
        if not builder.build():
            print("\n[ERROR] Build failed")
            return 1

    # Step 2: Flash firmware
    if not args.skip_flash:
        print_header("STEP 2: Flashing Firmware")
        uploader = FirmwareUploader(
            root_dir, args.board, args.port, args.baud, erase=args.erase
        )
        if not uploader.upload():
            print("\n[ERROR] Flash failed")
            return 1

    # Step 3: Upload application files
    if not args.skip_upload:
        print_header("STEP 3: Uploading Application Files")
        # Wait for device to stabilize after flashing
        print("Waiting for device to stabilize...")
        time.sleep(3)
        file_uploader = FileUploader(root_dir, args.port)
        if not file_uploader.upload_files():
            print("\n[ERROR] File upload failed")
            return 1

    # Step 4: Monitor
    if not args.skip_monitor:
        print_header("STEP 4: Monitoring Device")
        monitor = SerialMonitor(args.port, 115200)
        monitor.monitor()

    print_success("Deployment completed")
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="StripAlerts ESP32 Development CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build firmware")
    build_parser.add_argument(
        "--board",
        default="STRIPALERTS",
        help="ESP32 board variant (default: STRIPALERTS)",
    )
    build_parser.add_argument(
        "--clean", action="store_true", help="Clean before building"
    )
    build_parser.set_defaults(func=cmd_build)

    # Flash command
    flash_parser = subparsers.add_parser("flash", help="Flash firmware to device")
    flash_parser.add_argument(
        "--port", "-p", help="Serial port (auto-detect if not set)"
    )
    flash_parser.add_argument(
        "--baud", "-b", type=int, default=460800, help="Baud rate"
    )
    flash_parser.add_argument(
        "--board", default="STRIPALERTS", help="ESP32 board variant"
    )
    flash_parser.add_argument("--erase", action="store_true", help="Erase flash first")
    flash_parser.set_defaults(func=cmd_flash)

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload application files")
    upload_parser.add_argument(
        "--port", "-p", help="Serial port (auto-detect if not set)"
    )
    upload_parser.set_defaults(func=cmd_upload)

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor serial output")
    monitor_parser.add_argument(
        "--port", "-p", help="Serial port (auto-detect if not set)"
    )
    monitor_parser.add_argument(
        "--baud", "-b", type=int, default=115200, help="Baud rate"
    )
    monitor_parser.set_defaults(func=cmd_monitor)

    # Clean command
    clean_parser = subparsers.add_parser("clean", help="Clean build artifacts")
    clean_parser.add_argument(
        "--all", action="store_true", help="Clean everything including MicroPython"
    )
    clean_parser.set_defaults(func=cmd_clean)

    # Deploy command
    deploy_parser = subparsers.add_parser(
        "deploy", help="Full deployment (build + flash + upload + monitor)"
    )
    deploy_parser.add_argument(
        "--port", "-p", help="Serial port (auto-detect if not set)"
    )
    deploy_parser.add_argument(
        "--board", default="STRIPALERTS", help="ESP32 board variant"
    )
    deploy_parser.add_argument(
        "--baud", type=int, default=460800, help="Flash baud rate"
    )
    deploy_parser.add_argument(
        "--clean", action="store_true", help="Clean before building"
    )
    deploy_parser.add_argument("--erase", action="store_true", help="Erase flash first")
    deploy_parser.add_argument(
        "--skip-build", action="store_true", help="Skip build step"
    )
    deploy_parser.add_argument(
        "--skip-flash", action="store_true", help="Skip flash step"
    )
    deploy_parser.add_argument(
        "--skip-upload", action="store_true", help="Skip upload step"
    )
    deploy_parser.add_argument(
        "--skip-monitor", action="store_true", help="Skip monitor step"
    )
    deploy_parser.set_defaults(func=cmd_deploy)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
