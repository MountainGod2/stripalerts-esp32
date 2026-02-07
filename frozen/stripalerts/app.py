"""Main application module."""

import asyncio
import gc

from .api import ChaturbateAPI
from .config import settings
from .events import EventManager
from .led import LEDController, rainbow_pattern, solid_pattern
from .utils import log_info
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
        self.api: "ChaturbateAPI | None" = None
        self.ble = None

        if settings["ble_enabled"]:
             try:
                from .ble import BLEManager
                self.ble = BLEManager(settings["ble_name"])
             except ImportError:
                 log_info("BLE enabled but module not found (aioble missing?)")

        self._tasks: list = []
        self._running = False

    async def _handle_api_event(self, event: dict):
        """Handle API events."""
        # Example: Tip handling
        method = event.get("method")
        if method == "tip":
            log_info(f"Tip received: {event.get('object', {}).get('amount')}")
            # Flash Green
            self.led.set_pattern(solid_pattern(self.led, (0, 255, 0)))
            await asyncio.sleep(2)
            # Revert to rainbow
            self.led.set_pattern(
                rainbow_pattern(
                    self.led,
                    step=settings["rainbow_step"],
                    delay=settings["rainbow_delay"],
                )
            )

    async def setup(self) -> None:
        """Initialize components."""
        log_info("Setting up...")

        # Set default pattern
        self.led.set_pattern(
            rainbow_pattern(
                self.led, step=settings["rainbow_step"], delay=settings["rainbow_delay"]
            )
        )

        # Connect WiFi
        ssid = settings["wifi_ssid"]
        if ssid:
            if await self.wifi.connect(ssid, settings["wifi_password"]):
                # Start API if connected
                url = settings["api_url"]
                if url:
                    self.api = ChaturbateAPI(url, self.events)
                    self.events.on("api_event", self._handle_api_event)
            else:
                # Red for WiFi failure
                self.led.set_pattern(solid_pattern(self.led, (255, 0, 0)))

        if self.ble:
            # BLE setup usually simple, just need to start the task in run()
            pass

        gc.collect()

    async def run(self) -> None:
        """Main loop."""
        self._running = True

        # Hardware Tasks
        tasks = [asyncio.create_task(self.led.run())]

        # Event Processing
        tasks.append(asyncio.create_task(self.events.run()))

        # Network Tasks
        if self.api:
            tasks.append(asyncio.create_task(self.api.start()))

        if self.ble:
            tasks.append(asyncio.create_task(self.ble.start()))

        try:
            log_info("App started.")
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
