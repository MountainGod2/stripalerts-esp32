import uasyncio as asyncio
import neopixel
import machine

from .led import deg_to_rgb
from .constants import PIN_NUM, NUM_PIXELS


class App:
    def __init__(self):
        self.pin = machine.Pin(PIN_NUM, machine.Pin.OUT)
        self.np = neopixel.NeoPixel(self.pin, NUM_PIXELS)

    async def rainbow_cycle(self):
        while True:
            for deg in range(0, 360, 10):
                color = deg_to_rgb(deg)
                for i in range(NUM_PIXELS):
                    self.np[i] = color
                self.np.write()
                await asyncio.sleep(0.25)

    async def start(self):
        print("Starting StripAlerts...")
        print("Press Ctrl+C to stop.")
        asyncio.create_task(self.rainbow_cycle())

        while True:
            await asyncio.sleep(1)
