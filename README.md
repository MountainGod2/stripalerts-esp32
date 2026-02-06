# StripAlerts

ESP32-based LED strip controller with WiFi and BLE connectivity for real-time notifications and alerts.

## Features

- 🌈 **Multiple LED Patterns**: Rainbow cycle, solid color, blink, and more
- 📡 **WiFi Connectivity**: Connect to WiFi networks for remote control
- 📱 **Bluetooth Low Energy**: BLE support for local control
- ⚙️ **Configuration Management**: JSON-based configuration with persistence
- 🔄 **Event System**: Decoupled event-driven architecture
- 🔧 **OTA Updates**: Over-the-air firmware update support (experimental)

## Hardware Requirements

- ESP32-S3 development board (or compatible ESP32 variant)
- WS2812B/NeoPixel compatible LED strip
- USB cable for programming and power

## Project Structure

```
stripalerts-esp32/
├── boards/                    # Custom board definitions
│   └── STRIPALERTS_S3/       # StripAlerts ESP32-S3 board config
├── firmware/                  # Firmware build artifacts
│   ├── build/                # Compiled firmware binaries
│   └── micropython/          # MicroPython source (auto-cloned)
├── frozen/                    # Frozen Python modules
│   └── stripalerts/          # Main application package
│       ├── app.py            # Main application class
│       ├── ble.py            # Bluetooth Low Energy manager
│       ├── config.py         # Configuration management
│       ├── constants.py      # Application constants
│       ├── events.py         # Event bus system
│       ├── led.py            # LED controller and patterns
│       ├── ota.py            # Over-the-air updates
│       ├── utils.py          # Utility functions
│       ├── version.py        # Version information
│       └── wifi.py           # WiFi connection manager
├── src/                       # Source files uploaded to device
│   ├── boot.py               # Boot initialization
│   └── main.py               # Main entry point
├── tools/                     # Development tools
│   ├── builder.py            # Firmware builder
│   ├── cleaner.py            # Build cleaner
│   ├── cli.py                # Command-line interface
│   ├── monitor.py            # Serial monitor
│   ├── uploader.py           # Firmware/file uploader
│   └── utils.py              # Utility functions
├── Makefile                   # Build automation
├── pyproject.toml            # Project configuration
└── README.md                 # This file
```

## Quick Start

### Prerequisites

1. **ESP-IDF**: Install and configure ESP-IDF (required for building MicroPython)
   ```bash
   # Install ESP-IDF (follow official guide)
   git clone --recursive https://github.com/espressif/esp-idf.git
   cd esp-idf
   ./install.sh
   source export.sh
   ```

2. **Python Dependencies**: Install development dependencies
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or using pip
   pip install -e ".[dev]"
   ```

### Build and Deploy

#### Using Makefile (Recommended)

```bash
# Full deployment (build + flash + upload + monitor)
make deploy

# Individual commands
make build          # Build firmware only
make flash          # Flash firmware to device
make upload         # Upload application files
make monitor        # Monitor serial output
make clean          # Clean build artifacts
```

#### Using CLI Directly

```bash
# Full deployment
python3 tools/cli.py deploy --board STRIPALERTS_S3 --erase

# Individual commands
python3 tools/cli.py build --board STRIPALERTS_S3
python3 tools/cli.py flash --port /dev/ttyUSB0 --erase
python3 tools/cli.py upload --port /dev/ttyUSB0
python3 tools/cli.py monitor --port /dev/ttyUSB0
```

## Configuration

Create a `config.json` file on the ESP32 filesystem to customize settings:

```json
{
  "led_pin": 48,
  "num_pixels": 60,
  "led_timing": 1,
  "led_pattern": "rainbow",
  "rainbow_step": 10,
  "rainbow_delay": 0.25,
  "wifi_ssid": "YourNetworkName",
  "wifi_password": "YourPassword",
  "ble_enabled": false,
  "ble_name": "StripAlerts"
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `led_pin` | int | 48 | GPIO pin number for LED data |
| `num_pixels` | int | 1 | Number of LEDs in strip |
| `led_timing` | int | 1 | NeoPixel timing: 1=800kHz (default), 0=400kHz |
| `led_pattern` | string | "rainbow" | Active pattern name |
| `rainbow_step` | int | 10 | Degrees per rainbow cycle step |
| `rainbow_delay` | float | 0.25 | Delay between pattern updates |
| `wifi_ssid` | string | null | WiFi network name |
| `wifi_password` | string | null | WiFi password |
| `ble_enabled` | bool | false | Enable Bluetooth LE |
| `ble_name` | string | "StripAlerts" | BLE device name |

## ESP32 MicroPython Best Practices

This project follows ESP32 MicroPython best practices as outlined in the [official documentation](https://docs.micropython.org/en/latest/esp32/quickref.html):

### Networking
- Uses `network.WLAN()` default for station mode
- Uses `wlan.ipconfig('addr4')` instead of deprecated `ifconfig()`
- Implements `wlan.config(reconnects=n)` to control connection retry behavior
- Provides MAC address access via `wlan.config('mac')`

### NeoPixel/LED Control
- Supports both 800kHz (default) and 400kHz NeoPixel timing via `timing` parameter
- Uses RMT channel by default for low-level NeoPixel driving on ESP32
- Follows best practices from `machine.bitstream` documentation

### Temperature Monitoring
- Implements `esp32.mcu_temperature()` for ESP32-S3/S2/C3/C6 (Celsius)
- Implements `esp32.raw_temperature()` for original ESP32 (Fahrenheit)
- Note: Temperature reads higher than ambient due to IC warming

### Pin Usage
- Avoids pins 1 and 3 (REPL UART)
- Documents pin restrictions for ESP32 variants
- Ready for Pin drive strength and hold configuration when needed

### Memory Management
- Uses garbage collection strategically
- Stores constants in flash using `micropython.const()`
- Uses frozen modules to reduce RAM usage

### Power Management
- Supports CPU frequency adjustment via `machine.freq()`
- Ready for deep-sleep and RTC pin configuration when needed

## Development

### Adding New LED Patterns

1. Create a new pattern class in `frozen/stripalerts/led.py`:

```python
class MyPattern(LEDPattern):
    def __init__(self, param1, param2):
        self.param1 = param1
        self.param2 = param2
    
    async def update(self, controller: LEDController):
        # Your pattern logic here
        controller.fill((255, 0, 0))  # Red
        await asyncio.sleep(0.5)
```

2. Update the app to use your pattern:

```python
# In app.py setup() method
if pattern_name == "my_pattern":
    pattern = MyPattern(param1, param2)
    self.led_controller.set_pattern(pattern)
```

### Testing Changes

1. Make your changes to files in `frozen/stripalerts/` or `src/`
2. Rebuild and deploy:
   ```bash
   make deploy CLEAN=1
   ```

### Code Style

The project uses Ruff for linting and formatting:

```bash
# Check code style
ruff check .

# Format code
ruff format .
```

## Architecture

### Application Flow

1. **Boot** (`src/boot.py`): Basic initialization, garbage collection
2. **Main** (`src/main.py`): Entry point, error handling wrapper
3. **App Setup** (`app.py`): 
   - Load configuration
   - Initialize WiFi (if configured)
   - Initialize BLE (if enabled)
   - Setup LED controller with pattern
   - Start event system
4. **Main Loop**: 
   - LED controller runs pattern updates
   - Event system processes events
   - Main app monitors system state

### Module Responsibilities

- **app.py**: Application lifecycle management
- **config.py**: Configuration loading, saving, defaults
- **led.py**: LED hardware control and pattern abstractions
- **wifi.py**: WiFi station and AP management
- **ble.py**: Bluetooth Low Energy services
- **events.py**: Event bus for component communication
- **utils.py**: Logging and utility functions
- **ota.py**: Over-the-air update mechanism

## Troubleshooting

### Build Failures

**ESP-IDF not found**:
```bash
source $IDF_PATH/export.sh
```

**MicroPython clone fails**:
```bash
make clean-all
make build
```

### Flash Failures

**Device not detected**:
- Check USB cable connection
- Verify device appears in `/dev/` (Linux) or Device Manager (Windows)
- Try specifying port manually: `--port /dev/ttyUSB0`

**Permission denied**:
```bash
sudo usermod -a -G dialout $USER  # Linux
# Then log out and back in
```

### Runtime Issues

**LEDs not working**:
- Verify `led_pin` in config.json matches your hardware
- Check `num_pixels` is correct
- Ensure proper power supply for LED strip

**WiFi connection fails**:
- Verify SSID and password in config.json
- Check WiFi signal strength
- Review serial output for error messages

**Import errors**:
- Ensure firmware was built with frozen modules
- Verify manifest.py includes all required files
- Rebuild with `make build CLEAN=1`

## License

See [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with proper documentation
4. Test thoroughly
5. Submit a pull request

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting section

---

**Version**: 0.1.0  
**Last Updated**: 2026-02-05
