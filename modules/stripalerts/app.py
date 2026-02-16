"""Main application module."""

import asyncio
import gc

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    from typing import List, Optional

import machine

from .api import ChaturbateAPI
from .ble import BLEManager
from .config import settings
from .constants import COLOR_MAP, TRIGGER_TOKEN_AMOUNT
from .events import EventManager
from .led import (
    LEDController,
    blink_pattern,
    pulse_pattern,
    rainbow_pattern,
    solid_pattern,
)
from .utils import log_error, log_info
from .wifi import WiFiManager


class App:
    """Main application controller."""

    def __init__(self) -> None:
        """Initialize the application."""
        gc.collect()
        self.events = EventManager()

        self.led = LEDController(
            pin=settings["led_pin"],
            num_pixels=settings["num_pixels"],
            timing=settings.get("led_timing", 1),
        )

        self.wifi = WiFiManager()
        self.api: Optional[ChaturbateAPI] = None
        self.ble: Optional[BLEManager] = None
        self.mode = "BOOT"  # BOOT, NORMAL, PROVISIONING
        self._tasks: "List[asyncio.Task]" = []
        self._running = False
        self._current_effect_task = None
        self._current_hold_color: Optional[tuple[int, int, int]] = None
        self.wdt: Optional[machine.WDT] = None

    async def _handle_api_event(self, event: dict):
        """Handle API events."""
        method = event.get("method")
        if method == "tip":
            await self._handle_tip(event.get("object", {}).get("tip", {}))

    async def _handle_tip(self, tip_data: dict):
        """Handle individual tip events."""
        try:
            tokens = int(tip_data.get("tokens", 0))
        except (ValueError, TypeError) as e:
            log_error(f"Invalid token amount: {tip_data.get('tokens')} ({e})")
            tokens = 0

        message = tip_data.get("message", "").lower()
        log_info(f"Tip received: {tokens}")

        # Check for color trigger (35 tokens + color in message)
        found_color = self._parse_color_trigger(tokens, message)

        # Launch effect as background task to avoid blocking event loop
        if self._current_effect_task and not self._current_effect_task.done():
            self._current_effect_task.cancel()

        self._current_effect_task = asyncio.create_task(self._process_tip_effect(found_color))

    def _parse_color_trigger(self, tokens: int, message: str) -> Optional[tuple[int, int, int]]:
        """Check if tip triggers a specific color hold."""
        if tokens == TRIGGER_TOKEN_AMOUNT:
            for name, color in COLOR_MAP.items():
                if name in message:
                    return color
        return None

    async def _process_tip_effect(self, hold_color: "Optional[tuple[int, int, int]]" = None):
        """Handle the visual sequence for a tip."""
        try:
            # Pulse Green (Standard Tip Effect)
            self.led.set_pattern(pulse_pattern(self.led, (0, 255, 0), duration=2.0))
            await asyncio.sleep(2.1)  # Slightly longer than pattern duration

            # If it's a color trigger, switch to that color and hold
            if hold_color:
                log_info(f"Setting hold color: {hold_color}")
                self._current_hold_color = hold_color
                self.led.set_pattern(solid_pattern(self.led, hold_color))

                # Hold for 10 minutes
                await asyncio.sleep(600)

                # Revert after hold
                log_info("Hold complete, reverting to rainbow")
                self._current_hold_color = None

            # Restore State
            if self._current_hold_color:
                self.led.set_pattern(solid_pattern(self.led, self._current_hold_color))
            else:
                # Resume rainbow from saved position
                self.led.set_pattern(
                    rainbow_pattern(
                        self.led,
                        step=settings["rainbow_step"],
                        delay=settings["rainbow_delay"],
                        start_hue=self.led.rainbow_hue,
                    )
                )

        except asyncio.CancelledError:
            # Task was cancelled (new tip came in)
            pass
        except Exception as e:
            log_error(f"Effect error: {e}")

    async def setup(self) -> None:
        """Initialize components."""
        if self.wdt:
            self.wdt.feed()
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

        if self.wdt:
            self.wdt.feed()
        if ssid and api_url:
            log_info(f"Config found. Connecting to {ssid}...")
            if await self.wifi.connect(ssid, password, wdt=self.wdt):
                if self.wdt:
                    self.wdt.feed()
                log_info("WiFi Connected.")
                self.mode = "NORMAL"
                self.api = ChaturbateAPI(api_url, self.events)
                self.events.on("api_event", self._handle_api_event)
                return
            if self.wdt:
                self.wdt.feed()
            log_info("WiFi Connect Failed.")
        else:
            log_info("Missing Configuration (SSID or API URL).")

        # Fallback to Provisioning
        self.mode = "PROVISIONING"
        log_info("Entering Provisioning Mode...")

        self.led.set_pattern(blink_pattern(self.led, (0, 0, 255)))

        if self.wdt:
            self.wdt.feed()

        # Perform initial scan before starting BLE loop to avoid blocking connection
        log_info("Performing initial WiFi scan...")
        initial_networks = []
        try:
            initial_networks = await self.wifi.scan()
        except Exception as e:
            log_error(f"Initial scan failed: {e}")

        self.ble = BLEManager(self.wifi, initial_networks=initial_networks)

    async def run(self) -> None:
        """Run main loop."""
        self._running = True

        # LED is always running
        self._tasks.append(asyncio.create_task(self.led.run()))

        if self.mode == "NORMAL":
            self._tasks.append(asyncio.create_task(self.events.run()))
            if self.api:
                self._tasks.append(asyncio.create_task(self.api.start()))

        elif self.mode == "PROVISIONING":
            if self.ble:
                self._tasks.append(asyncio.create_task(self.ble.start()))
            else:
                log_error("BLE failed, staying in error mode")

        try:
            log_info(f"App started in {self.mode} mode.")
            while self._running:
                # Feed Watchdog
                if self.wdt:
                    self.wdt.feed()

                # Basic monitoring
                await asyncio.sleep(1)

                # Prune finished tasks
                for t in self._tasks[:]:
                    if t.done():
                        if not t.cancelled():
                            exc = t.exception()
                            if exc:
                                log_error(f"Task failed: {exc}")
                        self._tasks.remove(t)

                if not self._tasks:
                    log_info("All tasks finished.")
                    break

        except asyncio.CancelledError:
            log_info("Stopping...")
        except Exception as e:
            log_error(f"App runtime error: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Shut down the application and clean up resources."""
        self._running = False
        log_info("Shutting down...")
        if self.wdt:
            self.wdt.feed()

        for t in self._tasks:
            if not t.done():
                t.cancel()

        if self._current_effect_task and not self._current_effect_task.done():
            self._current_effect_task.cancel()
            self._tasks.append(self._current_effect_task)

        if self._tasks:
            if self.wdt:
                self.wdt.feed()

            gather_task = asyncio.create_task(asyncio.gather(*self._tasks, return_exceptions=True))

            feeder_task = None
            if self.wdt:

                async def _feed_watchdog_until_done():
                    try:
                        while not gather_task.done():
                            if self.wdt:
                                self.wdt.feed()
                            await asyncio.sleep(1)
                    except asyncio.CancelledError:
                        pass

                feeder_task = asyncio.create_task(_feed_watchdog_until_done())

            await gather_task

            if feeder_task and not feeder_task.done():
                feeder_task.cancel()
                try:
                    await feeder_task
                except asyncio.CancelledError:
                    pass

            self._tasks = []

        self._current_effect_task = None
        self.led.clear()
        log_info("Shutdown complete.")

    async def start(self):
        """Start the application."""
        self.wdt = machine.WDT(timeout=10000)
        await self.setup()
        await self.run()
