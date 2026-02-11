"""LED control module."""

import asyncio

import machine
import neopixel

import micropython
from micropython import const

from .utils import log_error

_HUE_MAX = const(360)


@micropython.native
def hsv_to_rgb(h: int, s: int = 255, v: int = 255):
    """Convert HSV to RGB (0-255).

    Returns:
        tuple[int, int, int]: RGB color values (0-255)

    """
    if s == 0:
        return (v, v, v)

    h = h % _HUE_MAX
    region = h // 60

    # Calculate intermediate values
    # Map remainder of 60 to 0-255: (h % 60) * 255 // 60
    # Equivalent to (h % 60) * 4.25
    f = (h % 60) * 17 // 4

    p = (v * (255 - s)) >> 8
    q = (v * (255 - ((s * f) >> 8))) >> 8
    t = (v * (255 - ((s * (255 - f)) >> 8))) >> 8

    if region == 0:
        return (v, t, p)
    if region == 1:
        return (q, v, p)
    if region == 2:
        return (p, v, t)
    if region == 3:
        return (p, q, v)
    if region == 4:
        return (t, p, v)
    return (v, p, q)


class LEDController:
    """Non-blocking LED Controller."""

    def __init__(self, pin: int, num_pixels: int, timing: int = 1) -> None:
        self.num_pixels = num_pixels
        self.np = neopixel.NeoPixel(machine.Pin(pin), num_pixels, timing=timing)
        self._pattern_gen = None
        self._running = False
        self._task = None
        self.clear()

    def set_pattern(self, pattern_generator) -> None:
        """Set the active pattern generator."""
        self._pattern_gen = pattern_generator

    def clear(self) -> None:
        """Clear the strip."""
        self.fill((0, 0, 0))

    def fill(self, color: "tuple[int, int, int]") -> None:
        """Fill strip with color immediately."""
        self.np.fill(color)
        self.np.write()

    async def run(self) -> None:
        """Main LED loop."""
        self._running = True
        while self._running:
            if self._pattern_gen:
                try:
                    # Pattern generator yields delay in seconds
                    delay = next(self._pattern_gen)
                    if delay is None:
                        # Stop if pattern is done
                        self._pattern_gen = None
                        delay = 0.1
                    await asyncio.sleep(delay)
                except StopIteration:
                    self._pattern_gen = None
                    await asyncio.sleep(0.1)
                except Exception as e:
                    # Log error but don't crash loop
                    log_error(f"LED Pattern Error: {e}")
                    self._pattern_gen = None
                    await asyncio.sleep(1)
            else:
                await asyncio.sleep(0.1)

    def stop(self) -> None:
        self._running = False


def solid_pattern(controller: LEDController, color: "tuple[int, int, int]"):
    """Generator for solid color."""
    controller.fill(color)
    while True:
        yield 1.0


def rainbow_pattern(controller: LEDController, step: float = 1, delay: float = 0.05):
    """Generator for rainbow effect."""
    hue = 0.0
    while True:
        color = hsv_to_rgb(int(hue))
        controller.fill(color)
        hue = (hue + step) % 360
        yield delay


def blink_pattern(
    controller: LEDController, color: "tuple[int, int, int]", duration: float = 0.5
):
    """Generator for blink effect."""
    while True:
        controller.fill(color)
        yield duration
        controller.clear()
        yield duration
