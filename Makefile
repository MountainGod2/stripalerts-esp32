.PHONY: help build upload monitor clean flash test

# Configuration - adjust these for your setup
PORT ?= /dev/ttyACM0
UPLOAD_METHOD ?= rshell

help:
	@echo "StripAlerts ESP32 Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  build     - Build MicroPython firmware with frozen modules"
	@echo "  upload    - Upload runtime code to ESP32 (default: rshell for ESP32-S3)"
	@echo "  monitor   - Connect to ESP32 serial monitor"
	@echo "  flash     - Flash firmware to ESP32"
	@echo "  clean     - Clean build artifacts"
	@echo "  test      - Run tests"
	@echo ""
	@echo "Configuration:"
	@echo "  PORT=$(PORT)"
	@echo "  UPLOAD_METHOD=$(UPLOAD_METHOD)"
	@echo ""
	@echo "Override with: make upload PORT=/dev/ttyUSB0 UPLOAD_METHOD=ampy"

build:
	@echo "Building firmware..."
	uv run python tools/build.py

upload:
	@echo "Uploading runtime code..."
	uv run python tools/upload.py --port $(PORT) --method $(UPLOAD_METHOD)

monitor:
	@echo "Starting monitor..."
	uv run python tools/monitor.py

flash: build
	@echo "Flashing firmware..."
	@echo "Note: Using ESP32-S3 configuration"
	esptool.py --chip esp32s3 --port $(PORT) --baud 460800 write_flash -z 0x0 firmware/build/firmware.bin

clean:
	@echo "Cleaning build artifacts..."
	rm -rf firmware/build/*.bin
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test:
	@echo "Running tests..."
	uv run pytest
