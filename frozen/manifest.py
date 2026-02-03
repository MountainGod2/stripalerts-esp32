"""
Manifest file for frozen modules in MicroPython firmware.
Modules listed here will be compiled into the firmware.
"""

# Freeze the stripalerts package using recommended package() function
package("stripalerts", base_path="$(BOARD_DIR)/../../frozen", opt=3)
