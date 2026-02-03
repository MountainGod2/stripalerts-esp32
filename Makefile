.PHONY: help build upload monitor clean deploy setup check

# Default board
BOARD ?= ESP32_GENERIC_S3

# Serial port (auto-detect if not specified)
PORT ?=

# Build options
BAUD ?= 460800
CLEAN ?=

# Python interpreter (use system Python, not uv's isolated env)
PYTHON := python3

help:
	@echo "StripAlerts ESP32 Firmware Build System"
	@echo ""
	@echo "Prerequisites:"
	@echo "  1. Source ESP-IDF: source \$$IDF_PATH/export.sh"
	@echo "  2. Install deps: uv sync"
	@echo ""
	@echo "Available targets:"
	@echo "  make build          - Build firmware (default: $(BOARD))"
	@echo "  make upload         - Upload firmware to device"
	@echo "  make monitor        - Monitor serial output"
	@echo "  make deploy         - Build + upload + monitor"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make clean-all      - Clean everything including MicroPython"
	@echo "  make check          - Check prerequisites"
	@echo ""
	@echo "Options:"
	@echo "  BOARD=<board>       - Set board variant (default: $(BOARD))"
	@echo "  PORT=<port>         - Set serial port (auto-detect if not set)"
	@echo "  BAUD=<rate>         - Set baud rate (default: $(BAUD))"
	@echo "  CLEAN=1             - Clean before building"
	@echo ""
	@echo "Examples:"
	@echo "  make build BOARD=ESP32_GENERIC"
	@echo "  make upload PORT=/dev/ttyUSB0"
	@echo "  make deploy CLEAN=1"

check:
	@$(PYTHON) tools/build.py --help > /dev/null 2>&1 || \
		(echo "[ERROR] Python tools not found. Run: uv sync" && exit 1)
	@if [ -z "$$IDF_PATH" ]; then \
		echo "[ERROR] IDF_PATH not set. Run: source \$$IDF_PATH/export.sh"; \
		exit 1; \
	fi
	@echo "[OK] Prerequisites check passed"

build: check
	@echo "Building firmware for $(BOARD)..."
	@if [ "$(CLEAN)" = "1" ]; then \
		$(PYTHON) tools/build.py --board $(BOARD) --clean; \
	else \
		$(PYTHON) tools/build.py --board $(BOARD); \
	fi

upload:
	@echo "Uploading firmware..."
	@if [ -n "$(PORT)" ]; then \
		$(PYTHON) tools/upload.py --board $(BOARD) --port $(PORT) --baud $(BAUD); \
	else \
		$(PYTHON) tools/upload.py --board $(BOARD) --baud $(BAUD); \
	fi

monitor:
	@echo "Starting serial monitor..."
	@if [ -n "$(PORT)" ]; then \
		$(PYTHON) tools/monitor.py --port $(PORT); \
	else \
		$(PYTHON) tools/monitor.py; \
	fi

clean:
	@$(PYTHON) tools/clean.py

clean-all:
	@$(PYTHON) tools/clean.py --all

deploy: build upload monitor

# Quick shortcuts
flash: upload
