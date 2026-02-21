# StripAlerts

MicroPython firmware for ESP32 LED strip control via WiFi and BLE.

## Hardware

- ESP32-based development board
- WS2812B/NeoPixel LED strip

## Development

### Dependencies

- [ESP-IDF](https://github.com/espressif/esp-idf)
- `uv sync` or `pip install -e ".[dev]"`

### Commands

```bash
make deploy   # Build, flash, upload, monitor
make build    # Build firmware
make flash    # Flash firmware
make upload   # Upload python modules
make monitor  # Serial monitor
```

## Configuration

`config.json`:

```json
{
  "led_pin": 48,
  "num_pixels": 60,
  "led_pattern": "rainbow",
  "api_url": "https://events.testbed.cb.dev/events/USERNAME/APITOKEN/",
  "wifi_ssid": "SSID",
  "wifi_password": "PASSWORD"
}
```

## Factory reset

- Hold the built-in `BOOT` button while powering on or resetting the board.
- Keep holding for about 5 seconds until reset confirmation is printed on serial.
- The device removes `config.json` and reboots into provisioning mode.
