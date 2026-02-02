"""
Manifest file for frozen modules in MicroPython firmware.
Modules listed here will be compiled into the firmware.
"""

# Freeze the stripalerts package
freeze("stripalerts", opt=3)  # noqa: F821
