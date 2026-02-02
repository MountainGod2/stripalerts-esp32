"""
Manifest file for frozen modules in MicroPython firmware.
Modules listed here will be compiled into the firmware.
"""

import os

# Get the frozen directory from environment variable
frozen_dir = os.environ.get("FROZEN_DIR", ".")

# Freeze the stripalerts package from the frozen directory
freeze(os.path.join(frozen_dir, "stripalerts"), opt=3)
