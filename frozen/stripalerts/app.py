"""Main application module for StripAlerts."""

try:
    from typing import Optional
except ImportError:
    pass

import gc

import uasyncio as asyncio

from .api import ChaturbateAPI
from .ble import BLEManager
from .config import settings
from .constants import COLOR_MAP
from .events import EventManager
from .led import LEDController, RainbowPattern, SolidColorPattern
from .utils import log_error, log_info
from .wifi import WiFiManager


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
        self.wifi: Optional[WiFiManager] = None
        self.ble: Optional[BLEManager] = None
        self.api: Optional[ChaturbateAPI] = None
        self._override_task: Optional[asyncio.Task] = None
        self._running = False

        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())

    async def setup(self) -> None:
        """Setup application components."""
        log_info("Setting up StripAlerts...")

        config = self.config

        wifi_ssid = config.get("wifi_ssid")
        wifi_password = config.get("wifi_password")

        has_error = False

        if wifi_ssid:
            self.wifi = WiFiManager()
            if await self.wifi.connect(wifi_ssid, wifi_password or ""):
                api_url = config.get("api_url")
                if api_url:
                    self.api = ChaturbateAPI(api_url, self.events)
                    self.events.on("api:tip", self._handle_tip)
                gc.collect()
            else:
                log_error("WiFi connection failed")
                # Display Red for connection failure
                self.led_controller.set_pattern(SolidColorPattern((255, 0, 0)))
                has_error = True
        else:
            log_error("No WiFi SSID configured")
            # Display Orange for missing configuration
            self.led_controller.set_pattern(SolidColorPattern((255, 100, 0)))
            has_error = True

        if config.get("ble_enabled", False):
            device_name = config.get("ble_name", "StripAlerts")
            self.ble = BLEManager(device_name)
            gc.collect()

        if not has_error:
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

        # Start API logic
        if self.api:
            asyncio.create_task(self.api.start())

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

        if self.api:
            self.api.stop()

        if self.ble:
            self.ble.deinit()

        log_info("Shutdown complete")

    async def _handle_tip(self, event_data: dict) -> None:
        """Handle tip events."""
        try:
            # Extract data
            payload = event_data.get("object", {})
            tip_data = payload.get("tip", {})
            tokens = tip_data.get("tokens", 0)
            # Handle string or int tokens just in case
            if isinstance(tokens, str) and tokens.isdigit():
                tokens = int(tokens)

            message = tip_data.get("message", "").lower().strip()

            if tokens == 35:
                # Check for exact match or if the message is a color name
                target_color = None
                if message in COLOR_MAP:
                    target_color = COLOR_MAP[message]

                if target_color:
                    log_info(f"Triggering color override: {message}")
                    await self._activate_override(target_color)
        except Exception as e:
            log_error(f"Error handling tip: {e}")

    async def _activate_override(self, color: tuple[int, int, int]) -> None:
        """Activate color override."""
        if self._override_task:
            self._override_task.cancel()

        pattern = SolidColorPattern(color)
        self.led_controller.set_pattern(pattern)

        # 10 minutes = 600 seconds
        self._override_task = asyncio.create_task(self._revert_after_delay(600))

    async def _revert_after_delay(self, delay: int) -> None:
        """Revert to default pattern after delay."""
        try:
            await asyncio.sleep(delay)
            # Revert to default
            self._restore_default_pattern()
        except asyncio.CancelledError:
            pass

    def _restore_default_pattern(self) -> None:
        """Restore the default LED pattern."""
        log_info("Restoring default pattern")
        pattern = RainbowPattern(
            step=self.config.get("rainbow_step", 1),
            delay=self.config.get("rainbow_delay", 0.1),
        )
        self.led_controller.set_pattern(pattern)
        self._override_task = None

    async def start(self) -> None:
        """Start the application (setup + run)."""
        try:
            await self.setup()
            await self.run()
        except Exception as e:
            log_error(f"Application error: {e}")
            await self.shutdown()
            raise
