import neopixel
import machine
import time

from stripalerts.led import deg_to_rgb
from stripalerts.constants import PIN_NUM, NUM_PIXELS

pin = machine.Pin(PIN_NUM, machine.Pin.OUT)
np = neopixel.NeoPixel(pin, NUM_PIXELS)

def rainbow_cycle():
    while True:
        for deg in range(0, 360, 10):
            color = deg_to_rgb(deg)
            r = int(color[0] * 255)
            g = int(color[1] * 255)
            b = int(color[2] * 255)
            np[0] = (r, g, b)
            np.write()
            time.sleep(0.1)
