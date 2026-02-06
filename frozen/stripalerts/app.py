"""Main application module for StripAlerts."""

import uasyncio as asyncio
import gc

from .led import LEDController, RainbowPattern
from .config import settings
from .events import EventManager
from .utils import log_info, log_error
from .wifi import WiFiManager
from .ble import BLEManager

try:
    from typing import Optional
except ImportError:
    pass


class App:
    """Main application class for StripAlerts."""

    def __init__(self) -> None:
        """Initialize the application."""
        gc.collect()

        self.config = settings
        self.events = EventManager()
        self.led_controller = LEDController(
            pin=self.config.get("led_pin", 48),
            num_pixels=self.config.get("num_pixels", 1),
            timing=self.config.get("led_timing", 1),
        )
        self.wifi: "Optional[WiFiManager]" = None
        self.ble: "Optional[BLEManager]" = None
        self._running = False

        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())

    async def setup(self) -> None:
        """Setup application components."""
        log_info("Setting up StripAlerts...")

        config = self.config

        wifi_ssid = config.get("wifi_ssid")
        wifi_password = config.get("wifi_password")

        if wifi_ssid:
            self.wifi = WiFiManager()
            log_info(f"Connecting to WiFi: {wifi_ssid}")
            await self.wifi.connect(wifi_ssid, wifi_password or "")
            gc.collect()

        if config.get("ble_enabled", False):
            device_name = config.get("ble_name", "StripAlerts")
            self.ble = BLEManager(device_name)
            gc.collect()

        pattern_name = config.get("led_pattern", "rainbow")
        if pattern_name == "rainbow":
            pattern = RainbowPattern(
                step=config.get("rainbow_step", 1),
                delay=config.get("rainbow_delay", 0.1),
            )
            self.led_controller.set_pattern(pattern)

        log_info("Setup complete")

    async def run(self) -> None:
        """Run the main application loop."""
        self._running = True
        log_info("Starting StripAlerts...")

        # Start LED controller
        asyncio.create_task(self.led_controller.run())

        # Start event processing
        asyncio.create_task(self.events.run())

        # Start BLE if enabled
        if self.ble:
            asyncio.create_task(self.ble.start())

        try:
            # Main loop
            while self._running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            log_info("Received interrupt signal")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shutdown the application."""
        log_info("Shutting down...")
        self._running = False

        if self.led_controller:
            self.led_controller.clear()

        if self.wifi:
            self.wifi.disconnect()

        if self.ble:
            self.ble.deinit()

        log_info("Shutdown complete")

    async def start(self) -> None:
        """Start the application (setup + run)."""
        try:
            await self.setup()
            await self.run()
        except Exception as e:
            log_error(f"Application error: {e}")
            await self.shutdown()
            raise
