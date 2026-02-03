#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


class FirmwareUploader:
    FLASH_ADDRESSES = {
        "bootloader": 0x1000,
        "partition-table": 0x8000,
        "firmware": 0x10000,
    }

    def __init__(
        self,
        root_dir: Path,
        port: str | None = None,
        baud: int = 460800,
        board: str = "ESP32_GENERIC_S3",
        erase: bool = False,
    ):
        self.root_dir = root_dir
        self.port = port
        self.baud = baud
        self.board = board
        self.erase = erase
        self.build_dir = root_dir / "firmware" / "build"
        self.chip = self._get_chip_type()

    def _get_chip_type(self) -> str:
        if "S3" in self.board:
            return "esp32s3"
        elif "S2" in self.board:
            return "esp32s2"
        elif "C3" in self.board:
            return "esp32c3"
        elif "C6" in self.board:
            return "esp32c6"
        else:
            return "esp32"

    def find_port(self) -> str | None:
        print("Auto-detecting ESP32 device...")

        try:
            # Try to use esptool's auto-detection
            result = subprocess.run(
                ["python", "-m", "esptool", "chip_id"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                # Parse output to find the port
                for line in result.stdout.split("\n"):
                    if "Serial port" in line:
                        port = line.split()[-1]
                        print(f"[OK] Found ESP32 on port: {port}")
                        return port

            # Fallback: check common ports
            import glob

            # Linux/macOS
            ports = (
                glob.glob("/dev/ttyUSB*")
                + glob.glob("/dev/ttyACM*")
                + glob.glob("/dev/cu.usb*")
            )

            if ports:
                port = ports[0]
                print(f"[OK] Using port: {port}")
                return port

            print("[ERROR] No ESP32 device found")
            return None

        except Exception as e:
            print(f"[WARNING] Auto-detection failed: {e}")
            return None

    def check_firmware_files(self) -> bool:
        """Check if firmware files exist."""
        print("Checking firmware files...")

        if not self.build_dir.exists():
            print(f"[ERROR] Build directory not found: {self.build_dir}")
            print("Please run 'build' command first")
            return False

        required_files = ["firmware.bin"]
        optional_files = ["bootloader.bin", "partition-table.bin"]

        missing_required = []
        for filename in required_files:
            if not (self.build_dir / filename).exists():
                missing_required.append(filename)

        if missing_required:
            print(
                f"[ERROR] Missing required firmware files: {', '.join(missing_required)}"
            )
            return False

        print("[OK] Required firmware files found")

        # Check optional files
        for filename in optional_files:
            if (self.build_dir / filename).exists():
                print(f"[OK] Found {filename}")

        return True

    def erase_flash(self, port: str) -> bool:
        """Erase the flash memory."""
        print("Erasing flash memory...")

        try:
            subprocess.run(
                ["python", "-m", "esptool", "--port", port, "erase_flash"], check=True
            )
            print("[OK] Flash erased successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to erase flash: {e}")
            return False

    def upload_firmware(self, port: str) -> bool:
        print(f"Uploading firmware to {port} at {self.baud} baud...")

        cmd = [
            "python",
            "-m",
            "esptool",
            "--chip",
            self.chip,
            "--port",
            port,
            "--baud",
            str(self.baud),
            "write_flash",
            "-z",
        ]

        firmware_bin = self.build_dir / "firmware.bin"
        bootloader_bin = self.build_dir / "bootloader.bin"
        partition_bin = self.build_dir / "partition-table.bin"

        if bootloader_bin.exists() and partition_bin.exists():
            cmd.extend(
                [
                    hex(self.FLASH_ADDRESSES["bootloader"]),
                    str(bootloader_bin),
                    hex(self.FLASH_ADDRESSES["partition-table"]),
                    str(partition_bin),
                    hex(self.FLASH_ADDRESSES["firmware"]),
                    str(firmware_bin),
                ]
            )
        else:
            cmd.extend(
                [
                    hex(self.FLASH_ADDRESSES["firmware"]),
                    str(firmware_bin),
                ]
            )

        try:
            subprocess.run(cmd, check=True)
            print("[OK] Firmware uploaded successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to upload firmware: {e}")
            return False

    def upload(self) -> bool:
        print("=" * 60)
        print("StripAlerts ESP32 Firmware Uploader")
        print("=" * 60)

        if not self.check_firmware_files():
            return False

        port = self.port
        if not port:
            port = self.find_port()
            if not port:
                print("\n[ERROR] Could not detect ESP32 device")
                print("Please specify port with --port option")
                return False

        if self.erase:
            if not self.erase_flash(port):
                return False

        if not self.upload_firmware(port):
            return False

        print("\n" + "=" * 60)
        print("[SUCCESS] Upload completed successfully")
        print("=" * 60)

        return True


def main():
    parser = argparse.ArgumentParser(description="Upload StripAlerts ESP32 firmware")
    parser.add_argument(
        "--port", "-p", help="Serial port (auto-detected if not specified)"
    )
    parser.add_argument(
        "--baud",
        "-b",
        type=int,
        default=460800,
        help="Baud rate for flashing (default: 460800)",
    )
    parser.add_argument(
        "--board",
        default="ESP32_GENERIC_S3",
        help="ESP32 board variant (default: ESP32_GENERIC_S3)",
    )
    parser.add_argument(
        "--erase", action="store_true", help="Erase flash before uploading"
    )

    args = parser.parse_args()

    root_dir = Path(__file__).parent.parent.resolve()

    uploader = FirmwareUploader(
        root_dir=root_dir,
        port=args.port,
        baud=args.baud,
        board=args.board,
        erase=args.erase,
    )

    success = uploader.upload()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
