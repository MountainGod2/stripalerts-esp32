"""Main application module."""

import asyncio
import gc

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    from typing import Optional

    from .ble import BLEManager

from .api import ChaturbateAPI
from .config import settings
from .constants import COLOR_MAP
from .events import EventManager
from .led import LEDController, rainbow_pattern, solid_pattern
from .utils import log_error, log_info
from .wifi import WiFiManager


class App:
    """Main application controller."""

    def __init__(self) -> None:
        gc.collect()
        self.events = EventManager()

        # Initialize Hardware
        self.led = LEDController(
            pin=settings["led_pin"],
            num_pixels=settings["num_pixels"],
            timing=settings.get("led_timing", 1),
        )

        self.wifi = WiFiManager()
        self.api: Optional[ChaturbateAPI] = None
        self.ble: Optional[BLEManager] = None
        self.mode = "BOOT"  # BOOT, NORMAL, PROVISIONING

        self._tasks: list = []
        self._running = False
        self._revert_task = None
        self._current_hold_color: Optional[tuple[int, int, int]] = None

    async def _handle_api_event(self, event: dict):
        """Handle API events."""
        # Example: Tip handling
        method = event.get("method")
        if method == "tip":
            tip_data = event.get("object", {}).get("tip", {})
            tokens = tip_data.get("tokens")
            message = tip_data.get("message", "").lower()
            log_info(f"Tip received: {tokens}")

            # Check for color trigger (35 tokens + color in message)
            found_color: Optional[tuple[int, int, int]] = None
            if tokens == 35:
                for name, color in COLOR_MAP.items():
                    if name in message:
                        found_color = color
                        break

            if found_color:
                log_info(f"Color trigger received: {found_color}")
                if self._revert_task:
                    self._revert_task.cancel()

                self._current_hold_color = found_color
                self.led.set_pattern(solid_pattern(self.led, found_color))
                self._revert_task = asyncio.create_task(self._revert_to_rainbow(600))
                return

            # Default behavior: Flash Green
            self.led.set_pattern(solid_pattern(self.led, (0, 255, 0)))
            await asyncio.sleep(2)

            # Restore previous state or rainbow
            if self._revert_task and self._current_hold_color:
                self.led.set_pattern(solid_pattern(self.led, self._current_hold_color))
            else:
                self.led.set_pattern(
                    rainbow_pattern(
                        self.led,
                        step=settings["rainbow_step"],
                        delay=settings["rainbow_delay"],
                    )
                )

    async def _revert_to_rainbow(self, delay: int):
        """Revert to rainbow pattern after delay."""
        try:
            await asyncio.sleep(delay)
            log_info("Reverting to rainbow pattern")
            self.led.set_pattern(
                rainbow_pattern(
                    self.led,
                    step=settings["rainbow_step"],
                    delay=settings["rainbow_delay"],
                )
            )
            self._current_hold_color = None
        except asyncio.CancelledError:
            pass
        finally:
            self._revert_task = None

    async def setup(self) -> None:
        """Initialize components."""
        log_info("Setting up...")

        # Set default pattern (Rainbow)
        self.led.set_pattern(
            rainbow_pattern(
                self.led, step=settings["rainbow_step"], delay=settings["rainbow_delay"]
            )
        )

        # Check Configuration
        ssid = settings["wifi_ssid"]
        password = settings["wifi_password"]
        api_url = settings["api_url"]

        if ssid and api_url:
            log_info(f"Config found. Connecting to {ssid}...")
            if await self.wifi.connect(ssid, password):
                log_info("WiFi Connected.")
                self.mode = "NORMAL"
                self.api = ChaturbateAPI(api_url, self.events)
                self.events.on("api_event", self._handle_api_event)
                return
            log_info("WiFi Connect Failed.")
        else:
            log_info("Missing Configuration (SSID or API URL).")

        # Fallback to Provisioning
        self.mode = "PROVISIONING"
        log_info("Entering Provisioning Mode...")

        # Indicate Provisioning Mode (Blue Pulse?)
        self.led.set_pattern(solid_pattern(self.led, (0, 0, 255)))

        try:
            from .ble import BLEManager

            self.ble = BLEManager(self)
        except ImportError:
            log_error("BLE module not found. Cannot provision.")
            self.led.set_pattern(solid_pattern(self.led, (255, 0, 0)))  # Red Error

    async def run(self) -> None:
        """Main loop."""
        self._running = True

        # LED is always running
        tasks = [asyncio.create_task(self.led.run())]

        if self.mode == "NORMAL":
            tasks.append(asyncio.create_task(self.events.run()))
            if self.api:
                tasks.append(asyncio.create_task(self.api.start()))

        elif self.mode == "PROVISIONING":
            if self.ble:
                tasks.append(asyncio.create_task(self.ble.start()))
            else:
                log_error("BLE failed, staying in error mode")

        try:
            log_info(f"App started in {self.mode} mode.")
            while self._running:
                await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            log_info("Stopping...")
        finally:
            self._running = False
            for t in tasks:
                t.cancel()
            self.led.clear()

    async def shutdown(self):
        self._running = False

    async def start(self):
        """Start the application."""
        await self.setup()
        await self.run()
