"""LED control and pattern management."""
from __future__ import annotations

import contextlib

with contextlib.suppress(ImportError):
    pass

import asyncio

import machine
import micropython
import neopixel

# micropython.constants
_HUE_MAX = micropython.const(360)
_REGION_SIZE = micropython.const(60)
_COLOR_MAX = micropython.const(255)


@micropython.native
def deg_to_rgb(deg: int) -> tuple[int, int, int]:
    """Convert degrees (Hue) to RGB colour (0-255).

    Args:
        deg: Degree value from 0 to 360 (Hue).

    Returns:
        RGB colour as a tuple of three integers from 0 to 255.

    """
    deg = deg % _HUE_MAX
    region = deg // _REGION_SIZE
    val = _COLOR_MAX
    x = (val * (deg % _REGION_SIZE)) // _REGION_SIZE

    if region == 0:
        return (val, x, 0)
    if region == 1:
        return (val - x, val, 0)
    if region == 2:
        return (0, val, x)
    if region == 3:
        return (0, val - x, val)
    if region == 4:
        return (x, 0, val)
    return (val, 0, val - x)


class LEDPattern:
    """Base class for LED patterns."""

    async def update(self, controller: LEDController) -> None:
        """Update the LED pattern.

        Args:
            controller: The LED controller instance

        """
        msg = "Subclasses must implement update()"
        raise NotImplementedError(msg)


class RainbowPattern(LEDPattern):
    """Rainbow cycling pattern."""

    def __init__(self, step: int = 1, delay: float = 0.1) -> None:
        """Initialize rainbow pattern.

        Args:
            step: Degree increment per update
            delay: Delay between updates in seconds

        """
        self.step = step
        self.delay = delay
        self.current_deg = 0

    @micropython.native
    async def update(self, controller: LEDController) -> None:
        """Update rainbow pattern."""
        color = deg_to_rgb(self.current_deg)
        controller.fill(color)
        self.current_deg = (self.current_deg + self.step) % int(_HUE_MAX)
        await asyncio.sleep(self.delay)


class SolidColorPattern(LEDPattern):
    """Solid color pattern."""

    def __init__(self, color: tuple[int, int, int]) -> None:
        """Initialize solid color pattern.

        Args:
            color: RGB color tuple (0-255 for each channel)

        """
        self.color = color

    @micropython.native
    async def update(self, controller: LEDController) -> None:
        """Update solid color pattern."""
        controller.fill(self.color)
        await asyncio.sleep(1)  # Long delay since nothing changes


class BlinkPattern(LEDPattern):
    """Blinking pattern."""

    def __init__(
        self, color: tuple[int, int, int], on_time: float = 0.5, off_time: float = 0.5
    ) -> None:
        """Initialize blink pattern.

        Args:
            color: RGB color tuple
            on_time: Time LED is on in seconds
            off_time: Time LED is off in seconds

        """
        self.color = color
        self.on_time = on_time
        self.off_time = off_time
        self.state = False

    @micropython.native
    async def update(self, controller: LEDController) -> None:
        """Update blink pattern."""
        if self.state:
            controller.fill(self.color)
            await asyncio.sleep(self.on_time)
        else:
            controller.clear()
            await asyncio.sleep(self.off_time)
        self.state = not self.state


class LEDController:
    """Controls NeoPixel LEDs with pattern support."""

    def __init__(self, pin: int, num_pixels: int, timing: int = 1) -> None:
        """Initialize LED controller.

        Args:
            pin: GPIO pin number
            num_pixels: Number of pixels in the strip
            timing: 1 for 800kHz (default), 0 for 400kHz devices

        """
        self.pin = machine.Pin(pin, machine.Pin.OUT)
        self.num_pixels = num_pixels
        # Pass timing parameter to support different NeoPixel types
        self.np = neopixel.NeoPixel(self.pin, num_pixels, timing=timing)
        self.pattern: LEDPattern | None = None
        self._running = False

    def set_pattern(self, pattern: LEDPattern) -> None:
        """Set the active LED pattern.

        Args:
            pattern: LED pattern to activate

        """
        self.pattern = pattern

    def set_pixel(self, index: int, color: tuple[int, int, int]) -> None:
        """Set individual pixel color.

        Args:
            index: Pixel index
            color: RGB color tuple

        """
        if 0 <= index < self.num_pixels:
            self.np[index] = color

    @micropython.native
    def fill(self, color: tuple[int, int, int]) -> None:
        """Fill all pixels with a color.

        Args:
            color: RGB color tuple

        """
        for i in range(self.num_pixels):
            self.np[i] = color
        self.np.write()

    def clear(self) -> None:
        """Turn off all LEDs."""
        self.fill((0, 0, 0))

    async def run(self) -> None:
        """Run the LED controller with the active pattern."""
        self._running = True
        while self._running:
            if self.pattern:
                await self.pattern.update(self)
            else:
                await asyncio.sleep(0.1)

    def stop(self) -> None:
        """Stop the LED controller."""
        self._running = False
