.PHONY: help build upload monitor clean flash flash-only validate

# Configuration
BOARD ?= ESP32_GENERIC_S3
PORT ?= /dev/ttyACM0
BAUD ?= 460800
DEVICE ?= a0

help:
	@echo "StripAlerts ESP32 Makefile"
	@echo ""
	@echo "Configuration:"
	@echo "  BOARD=<board>  - Board type (default: esp32s3)"
	@echo "  PORT=<port>    - Serial port (default: /dev/ttyACM0)"
	@echo "  BAUD=<baud>    - Baud rate (default: 460800)"
	@echo "  DEVICE=<dev>   - mpremote device (default: a0)"
	@echo ""
	@echo "Available targets:"
	@echo "  build         - Build MicroPython firmware with frozen modules"
	@echo "  flash         - Build and flash firmware to ESP32"
	@echo "  flash-only    - Flash existing firmware (skip build)"
	@echo "  upload        - Upload runtime code to ESP32"
	@echo "  monitor       - Connect to ESP32 serial monitor"
	@echo "  validate      - Validate ESP32 filesystem"
	@echo "  clean         - Clean build artifacts"
	@echo ""
	@echo "Examples:"
	@echo "  make build"
	@echo "  make flash PORT=/dev/ttyUSB0"
	@echo "  make upload DEVICE=a1"
	@echo "  make monitor PORT=/dev/ttyACM0"

build:
	@echo "Building firmware for $(BOARD)..."
	uv run tools/build.py --chip esp32s3 --board $(BOARD) --port $(PORT)

flash: build
	@echo "Flashing firmware to $(PORT)..."
	uv run tools/build.py --flash --chip esp32s3 --board $(BOARD) --port $(PORT) --device $(DEVICE)

flash-only:
	@echo "Flashing existing firmware to $(PORT)..."
	@if [ ! -f firmware/build/firmware.bin ]; then \
		echo "Error: firmware/build/firmware.bin not found"; \
		echo "Run 'make build' first"; \
		exit 1; \
	fi
	esptool.py --chip $(BOARD) --port $(PORT) --baud $(BAUD) erase_flash
	esptool.py --chip $(BOARD) --port $(PORT) --baud $(BAUD) write_flash -z 0x0 firmware/build/firmware.bin
	@echo "Flashing complete. Validating filesystem..."
	@sleep 3
	mpremote $(DEVICE) eval "1+1" || echo "Device not yet responding"

upload:
	@echo "Uploading runtime code..."
	uv run tools/upload.py --port $(PORT) --device $(DEVICE)

monitor:
	@echo "Starting serial monitor on $(PORT)..."
	mpremote $(DEVICE) repl

validate:
	@echo "Validating ESP32 filesystem..."
	@mpremote $(DEVICE) eval "1+1" && echo "[OK] Device responding" || (echo "[FAIL] Device not responding"; exit 1)
	@mpremote $(DEVICE) exec "import os; print('[OK] Filesystem:', len(os.listdir('/')), 'items')" || echo "[FAIL] Filesystem error"

clean:
	@echo "Cleaning build artifacts..."
	rm -rf firmware/build/*.bin
	rm -rf firmware/build/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Clean complete"

.DEFAULT_GOAL := help