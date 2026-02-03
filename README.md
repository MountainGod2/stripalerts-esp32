# StripAlerts

MicroPython firmware for the Chaturbate Events API on ESP32.

## Quick Start

### Prerequisites

1. **ESP-IDF v5.0+** - Required for building firmware
   ```bash
   # Install ESP-IDF (if not already installed)
   # Follow: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/
   
   # Set IDF_PATH environment variable
   export IDF_PATH=$HOME/esp/esp-idf
   ```

2. **Python 3.9+** with uv package manager
   ```bash
   # Install uv if not already installed
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

### Installation

```bash
# Install dependencies
uv sync
```

### ESP-IDF Integration with uv

The build scripts work with ESP-IDF in two ways:

**Option 1: Source ESP-IDF environment (Recommended)**
```bash
# Source ESP-IDF export script (adds tools to PATH)
source $IDF_PATH/export.sh
# Or use your alias: get_idf

# Now run build commands
uv run build
uv run deploy
```

**Option 2: Automatic detection**
```bash
# Just set IDF_PATH, the build script will find idf.py automatically
export IDF_PATH=$HOME/esp/esp-idf
uv run build
```

The build script automatically:
- Detects `idf.py` from PATH or `$IDF_PATH/tools/idf.py`
- Preserves ESP-IDF environment variables
- Uses the correct Python interpreter

### Building and Deploying

#### Complete Workflow
Build, upload, and monitor in one command:
```bash
# Source ESP-IDF first
source $IDF_PATH/export.sh

# Then deploy
uv run deploy
```

#### Step by Step

1. **Build firmware:**
   ```bash
   uv run build
   ```

2. **Upload to device:**
   ```bash
   uv run upload
   ```

3. **Monitor serial output:**
   ```bash
   uv run monitor
   ```

### Available Commands

| Command | Description |
|---------|-------------|
| `uv run build` | Build custom MicroPython firmware |
| `uv run upload` | Flash firmware to ESP32 device |
| `uv run monitor` | Monitor serial output |
| `uv run clean` | Clean build artifacts |
| `uv run deploy` | Build + upload + monitor |

### Common Options

**Build:**
```bash
uv run build --board ESP32_GENERIC  # Specify different board variant
uv run build --clean                # Clean build
```

**Upload:**
```bash
uv run upload --port /dev/ttyUSB0      # Specify port
uv run upload --erase                  # Erase flash first
uv run upload --baud 115200            # Custom baud rate
```

**Monitor:**
```bash
uv run monitor --port /dev/ttyUSB0     # Specify port
uv run monitor --filter "[ERROR]"      # Filter output
```

**Deploy:**
```bash
uv run deploy --clean --erase          # Full clean deployment
uv run deploy --skip-build             # Upload existing build
```

## Troubleshooting

### "idf.py not found in PATH"

Make sure you've sourced the ESP-IDF environment:
```bash
source $IDF_PATH/export.sh
```

Or ensure `IDF_PATH` is set:
```bash
export IDF_PATH=$HOME/esp/esp-idf
```

### ESP-IDF not installed

Install ESP-IDF v5.0 or later:
```bash
mkdir -p ~/esp
cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32
```

Then source it:
```bash
source ~/esp/esp-idf/export.sh
```

## Project Structure

```
stripalerts-esp32/
├── firmware/          # Firmware build directory
│   ├── build/        # Built firmware binaries
│   └── micropython/  # MicroPython source (auto-cloned)
├── frozen/           # Modules to freeze into firmware
│   └── stripalerts/  # Core application modules
├── src/              # Source files for development
│   ├── boot.py      # Boot configuration
│   ├── main.py      # Main entry point
│   └── stripalerts/ # Application modules
├── tools/            # Build and deployment scripts
│   ├── build.py     # Firmware builder
│   ├── upload.py    # Firmware uploader
│   ├── monitor.py   # Serial monitor
│   ├── clean.py     # Build cleaner
│   └── deploy.py    # Complete workflow
└── pyproject.toml    # Project configuration
```

## Development

### Frozen vs Unfrozen Modules

**Frozen modules** (`frozen/stripalerts/`):
- Pre-compiled into firmware bytecode
- Execute directly from flash memory (saves RAM)
- Faster loading, no runtime compilation
- Best for production deployments
- Requires firmware rebuild for changes

**Unfrozen modules** (`src/stripalerts/`):
- Loaded from filesystem at runtime
- Can be updated without reflashing firmware
- Uses more RAM
- Best for active development
- Faster iteration during development

### Supported Boards

- ESP32_GENERIC_S3 (default)
- ESP32_GENERIC
- ESP32_GENERIC_S2
- ESP32_GENERIC_C3

## License

See LICENSE file for details.
