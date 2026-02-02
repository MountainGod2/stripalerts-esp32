from micropython import neopixel
import machine
import time

from stripalerts.led import deg_to_rgb

pin_num = 48
num_pixels = 1
pin = machine.Pin(pin_num, machine.Pin.OUT)
np = neopixel.NeoPixel(pin, num_pixels)


def main():
    while True:
        for deg in range(0, 360, 10):
            color = deg_to_rgb(deg)
            r = int(color[0] * 255)
            g = int(color[1] * 255)
            b = int(color[2] * 255)
            neopixel[0] = (r, g, b)
            neopixel.write()
            time.sleep(0.1)
