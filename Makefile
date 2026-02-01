.PHONY: help build upload monitor clean flash test

help:
	@echo "StripAlerts ESP32 Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  build     - Build MicroPython firmware with frozen modules"
	@echo "  upload    - Upload runtime code to ESP32"
	@echo "  monitor   - Connect to ESP32 serial monitor"
	@echo "  flash     - Flash firmware to ESP32"
	@echo "  clean     - Clean build artifacts"
	@echo "  test      - Run tests"

build:
	@echo "Building firmware..."
	uv run python tools/build.py

upload:
	@echo "Uploading runtime code..."
	uv run python tools/upload.py

monitor:
	@echo "Starting monitor..."
	uv run python tools/monitor.py

flash: build
	@echo "Flashing firmware..."
	@echo "Note: Using ESP32-S3 configuration"
	esptool.py --chip esp32s3 --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x0 firmware/build/firmware.bin

clean:
	@echo "Cleaning build artifacts..."
	rm -rf firmware/build/*.bin
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test:
	@echo "Running tests..."
	uv run pytest
