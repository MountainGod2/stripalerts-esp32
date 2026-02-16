"""LED control module."""

import asyncio

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    from typing import Optional

import machine
import neopixel

import micropython
from micropython import const

from .constants import LED_BRIGHTNESS
from .utils import log_error

_HUE_MAX = const(360)


@micropython.native
def hsv_to_rgb(h: float, s: int = 255, v: int = 255):
    """Convert HSV to RGB (0-255).

    Returns:
        tuple[int, int, int]: RGB color values (0-255)

    """
    if s == 0:
        return (v, v, v)

    h_float = float(h) % _HUE_MAX

    region = int(h_float // 60)
    remainder = h_float - (region * 60)

    # Map remainder (0-60) to 0-255
    f = int(remainder * 255 / 60)

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
        """Initialize LED controller.

        Args:
            pin: GPIO pin number for LED data
            num_pixels: Number of LEDs in the strip
            timing: Timing mode (0 or 1 for different LED types)

        """
        self.num_pixels = num_pixels
        self.np = neopixel.NeoPixel(machine.Pin(pin), num_pixels, timing=timing)
        self._pattern_gen = None
        self._running = False
        self._task = None
        self._saved_rainbow_hue = 0.0  # Track rainbow position
        self.clear()

    def set_pattern(self, pattern_generator) -> None:
        """Set the active pattern generator."""
        self._pattern_gen = pattern_generator

    def clear(self) -> None:
        """Clear the strip."""
        self.fill((0, 0, 0))

    def fill(self, color: "tuple[int, int, int]") -> None:
        """Fill strip with color immediately."""
        r = int(color[0] * LED_BRIGHTNESS)
        g = int(color[1] * LED_BRIGHTNESS)
        b = int(color[2] * LED_BRIGHTNESS)
        self.np.fill((r, g, b))
        self.np.write()

    async def run(self) -> None:
        """Run main LED loop."""
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
        """Stop the LED controller loop."""
        self._running = False


def solid_pattern(controller: LEDController, color: "tuple[int, int, int]"):
    """Generate solid color pattern."""
    controller.fill(color)
    while True:
        yield 1.0


def rainbow_pattern(
    controller: LEDController,
    step: float = 1,
    delay: float = 0.05,
    start_hue: Optional[float] = None,
):
    """Generate rainbow effect pattern.

    Args:
        controller: LED controller instance
        step: Hue increment per iteration
        delay: Delay between updates in seconds
        start_hue: Optional starting hue (0-360). If None, uses saved hue from
            controller.

    """
    if start_hue is None:
        hue = controller._saved_rainbow_hue
    else:
        hue = start_hue

    while True:
        color = hsv_to_rgb(hue)
        controller.fill(color)
        hue = (hue + step) % 360
        controller._saved_rainbow_hue = hue
        yield delay


def pulse_pattern(
    controller: LEDController,
    color: "tuple[int, int, int]",
    duration: float = 2.0,
    steps: int = 50,
):
    """Generate smooth pulsing effect pattern.

    Args:
        controller: LED controller instance
        color: RGB color to pulse
        duration: Total duration of the pulse effect in seconds
        steps: Number of brightness steps (higher = smoother)

    """
    import math

    delay = duration / steps
    for i in range(steps):
        # Create a sine wave for smooth brightness (0 to 1 to 0)
        brightness = math.sin((i / (steps - 1)) * math.pi)
        r = int(color[0] * brightness)
        g = int(color[1] * brightness)
        b = int(color[2] * brightness)
        controller.fill((r, g, b))
        yield delay


def blink_pattern(controller: LEDController, color: "tuple[int, int, int]", duration: float = 0.5):
    """Generate blink effect pattern."""
    while True:
        controller.fill(color)
        yield duration
        controller.clear()
        yield duration
