"""Main application module."""

import asyncio
import gc

import machine

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    from typing import List, Optional

from .api import ChaturbateAPI
from .ble import BLEManager
from .config import settings
from .constants import COLOR_MAP, TRIGGER_TOKEN_AMOUNT
from .events import EventManager
from .led import LEDController, rainbow_pattern, solid_pattern
from .utils import log_error, log_info
from .wifi import WiFiManager


class App:
    """Main application controller."""

    def __init__(self) -> None:
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

        if TYPE_CHECKING:
            self._tasks: List[asyncio.Task] = []
        else:
            self._tasks = []
        self._running = False
        self._revert_task = None
        self._current_hold_color: Optional[tuple[int, int, int]] = None

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

        if found_color:
            await self._activate_hold_color(found_color)
        else:
            await self._activate_flash_effect()

    def _parse_color_trigger(
        self, tokens: int, message: str
    ) -> "Optional[tuple[int, int, int]]":
        """Check if tip triggers a specific color hold."""
        if tokens == TRIGGER_TOKEN_AMOUNT:
            for name, color in COLOR_MAP.items():
                if name in message:
                    return color
        return None

    async def _activate_hold_color(self, color: "tuple[int, int, int]"):
        """Activate a solid color hold for 10 minutes."""
        log_info(f"Color trigger received: {color}")
        if self._revert_task:
            self._revert_task.cancel()

        self._current_hold_color = color
        self.led.set_pattern(solid_pattern(self.led, color))
        self._revert_task = asyncio.create_task(self._revert_to_rainbow(600))

    async def _activate_flash_effect(self):
        """Flash green for a standard tip."""
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

        self.wdt.feed()
        if ssid and api_url:
            log_info(f"Config found. Connecting to {ssid}...")
            if await self.wifi.connect(ssid, password):
                self.wdt.feed()
                log_info("WiFi Connected.")
                self.mode = "NORMAL"
                self.api = ChaturbateAPI(api_url, self.events)
                self.events.on("api_event", self._handle_api_event)
                return
            self.wdt.feed()
            log_info("WiFi Connect Failed.")
        else:
            log_info("Missing Configuration (SSID or API URL).")

        # Fallback to Provisioning
        self.mode = "PROVISIONING"
        log_info("Entering Provisioning Mode...")

        # Indicate Provisioning Mode (Blue Pulse?)
        self.led.set_pattern(solid_pattern(self.led, (0, 0, 255)))

        self.wdt.feed()
        self.ble = BLEManager(self.wifi)

    async def run(self) -> None:
        """Main loop."""
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
        self._running = False
        log_info("Shutting down...")

        for t in self._tasks:
            if not t.done():
                t.cancel()

        if self._revert_task and not self._revert_task.done():
            self._revert_task.cancel()
            self._tasks.append(self._revert_task)

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks = []

        self._revert_task = None
        self.led.clear()
        log_info("Shutdown complete.")

    async def start(self):
        """Start the application."""
        self.wdt = machine.WDT(timeout=10000)
        await self.setup()
        await self.run()
