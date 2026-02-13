.PHONY: help build flash upload monitor clean clean-all deploy check
.DEFAULT_GOAL := help

# Configuration
BOARD ?= STRIPALERTS_S3
PORT ?=
BAUD ?= 460800

# Tools
VENV_PYTHON := .venv/bin/python
ifneq ($(wildcard $(VENV_PYTHON)),)
    PYTHON ?= $(VENV_PYTHON)
else
    PYTHON ?= python3
endif
CLI := $(PYTHON) tools/cli.py

help: ## Show this help message
	@echo "StripAlerts ESP32 Firmware Build System"
	@echo ""
	@echo "Prerequisites:"
	@echo "  1. Source ESP-IDF: source \$$IDF_PATH/export.sh"
	@echo "  2. Install deps: uv sync"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'
	@echo ""
	@echo "Options:"
	@echo "  BOARD=<board>    Board variant (default: $(BOARD))"
	@echo "  PORT=<port>      Serial port (auto-detect if not set)"
	@echo "  BAUD=<rate>      Baud rate (default: $(BAUD))"
	@echo "  CLEAN=1          Clean before building"
	@echo ""
	@echo "Examples:"
	@echo "  make build"
	@echo "  make flash PORT=/dev/ttyUSB0"
	@echo "  make deploy CLEAN=1"

check: ## Check prerequisites
	@$(CLI) --help > /dev/null 2>&1 || \
		(echo "[ERROR] Python tools not found. Run: uv sync" && exit 1)
	@if [ -z "$$IDF_PATH" ]; then \
		echo "[ERROR] IDF_PATH not set. Run: source \$$IDF_PATH/export.sh"; \
		exit 1; \
	fi
	@echo "[OK] Prerequisites check passed"

build: check ## Build firmware
	@$(CLI) build --board $(BOARD) $(if $(CLEAN),--clean)

flash: ## Flash firmware to device
	@$(CLI) flash --board $(BOARD) --baud $(BAUD) --erase $(if $(PORT),--port $(PORT))

upload: ## Upload application files to device
	@$(CLI) upload $(if $(PORT),--port $(PORT))

monitor: ## Monitor serial output
	@$(CLI) monitor $(if $(PORT),--port $(PORT))

clean: ## Clean build artifacts
	@$(CLI) clean

clean-all: ## Clean everything including MicroPython
	@$(CLI) clean --all

deploy: check ## Full deployment (build + flash + upload + monitor)
	@$(CLI) deploy --board $(BOARD) --baud $(BAUD) $(if $(CLEAN),--clean) $(if $(PORT),--port $(PORT))
