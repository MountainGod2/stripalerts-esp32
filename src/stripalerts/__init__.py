from micropython import neopixel
import machine
import time

from stripalerts.led import deg_to_rgb

pin = machine.Pin.board.D48
neopixel = neopixel.NeoPixel(pin, 1)

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