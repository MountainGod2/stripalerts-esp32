# StripAlerts ESP32 Firmware Build System
.PHONY: help install check build flash upload monitor clean clean-all deploy deploy-quick test lint format typecheck watch shell ls reset info version
.DEFAULT_GOAL := help
.SILENT: check

BOARD ?= STRIPALERTS_S3
PORT ?=
BAUD ?= 460800
MONITOR_BAUD ?= 115200

VENV_PYTHON := .venv/bin/python
PYTHON := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python3)
CLI := $(PYTHON) -m tools.cli

help:
	@echo "=========================================================================="
	@echo "StripAlerts ESP32 Firmware Build System"
	@echo "=========================================================================="
	@echo ""
	@echo "Prerequisites:"
	@echo "  1. Source ESP-IDF environment:"
	@echo "     source \$$IDF_PATH/export.sh"
	@echo "  2. Install Python dependencies:"
	@echo "     uv sync --all-extras"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Configuration options:"
	@echo "  BOARD=$(BOARD)           Board variant"
	@echo "  PORT=$(if $(PORT),$(PORT),<auto>)              Serial port"
	@echo "  BAUD=$(BAUD)             Flash baud rate"
	@echo "  MONITOR_BAUD=$(MONITOR_BAUD)     Monitor baud rate"
	@echo ""
	@echo "Additional options:"
	@echo "  CLEAN=1                  Clean before building"
	@echo "  ERASE=1                  Erase flash before flashing"
	@echo "  VERBOSE=1                Show verbose output"
	@echo ""
	@echo "Examples:"
	@echo "  make build"
	@echo "  make flash PORT=/dev/ttyUSB0"
	@echo "  make deploy CLEAN=1 ERASE=1"
	@echo "  make build BOARD=STRIPALERTS VERBOSE=1"
	@echo ""

install: ## Install Python dependencies with uv
	@echo "Installing dependencies..."
	uv sync --all-extras --frozen
	@echo "Dependencies installed successfully"

check: ## Check prerequisites (ESP-IDF, tools, etc.)
	@$(CLI) --help > /dev/null 2>&1 || \
		(echo "ERROR: Python tools not found. Run: make install" && exit 1)
	@if [ -z "$$IDF_PATH" ]; then \
		echo "ERROR: IDF_PATH not set. Run: source \$$IDF_PATH/export.sh"; \
		exit 1; \
	fi
	@echo "Prerequisites check passed"

build: check ## Build firmware for specified board
	$(CLI) build --board $(BOARD) $(if $(CLEAN),--clean) $(if $(VERBOSE),--verbose)

flash: ## Flash firmware to device
	$(CLI) flash --board $(BOARD) \
		$(if $(PORT),--port $(PORT)) \
		--baud $(BAUD) \
		$(if $(ERASE),--erase)

upload: ## Upload application files to device
	$(CLI) upload $(if $(PORT),--port $(PORT))

monitor: ## Monitor serial output from device
	$(CLI) monitor $(if $(PORT),--port $(PORT)) --baud $(MONITOR_BAUD)

deploy: ## Complete deployment (build → flash → upload → monitor)
	$(CLI) deploy --board $(BOARD) \
		$(if $(PORT),--port $(PORT)) \
		--baud $(BAUD) \
		$(if $(CLEAN),--clean) \
		$(if $(ERASE),--erase)

deploy-quick: ## Quick deployment (skip build/flash, only upload + monitor)
	$(CLI) deploy --skip-build --skip-flash $(if $(PORT),--port $(PORT))

clean: ## Clean build artifacts (dist/ and build-*)
	$(CLI) clean

clean-all: ## Deep clean including MicroPython artifacts
	$(CLI) clean --all

lint: ## Run ruff linter on tools and source code
	@echo "Running linter..."
	$(PYTHON) -m ruff check tools/ src/ modules/ --fix
	@echo "Linting complete"

format: ## Format code with ruff
	@echo "Formatting code..."
	$(PYTHON) -m ruff format tools/ src/ modules/
	@echo "Formatting complete"

typecheck: ## Run type checking with mypy
	@echo "Running type checker..."
	$(PYTHON) -m mypy src/ modules/
	@echo "Type checking complete"

test: lint typecheck ## Run all code quality checks

watch: ## Build in watch mode (rebuild on file changes)
	@echo "Watching for changes (experimental)..."
	@while true; do \
		inotifywait -r -e modify src/ modules/ boards/ 2>/dev/null && \
		make build BOARD=$(BOARD); \
	done

shell: ## Open Python REPL on device
	mpremote connect $(if $(PORT),$(PORT),auto) repl

ls: ## List files on device filesystem
	mpremote connect $(if $(PORT),$(PORT),auto) ls

reset: ## Soft-reset device
	mpremote connect $(if $(PORT),$(PORT),auto) soft-reset

info: ## Show build configuration and tool information
	@echo "Build Configuration:"
	@echo "  Board:        $(BOARD)"
	@echo "  Port:         $(if $(PORT),$(PORT),<auto-detect>)"
	@echo "  Flash Baud:   $(BAUD)"
	@echo "  Monitor Baud: $(MONITOR_BAUD)"
	@echo ""
	@echo "Tool Information:"
	@echo "  Python:       $$($(PYTHON) --version)"
	@echo "  ESP-IDF:      $${IDF_PATH:-<not set>}"
	@echo "  Virtual Env:  $(if $(wildcard $(VENV_PYTHON)),Active,Not active)"
	@echo ""

version: ## Show project version
	@grep '^version' pyproject.toml | cut -d '"' -f2
