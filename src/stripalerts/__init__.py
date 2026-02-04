"""StripAlerts package.

This package combines:
- Frozen modules compiled into firmware (e.g., constants.py)
- Filesystem modules uploaded at runtime (e.g., app.py, ble.py)
"""

# Re-export constants from frozen module
from .constants import PIN_NUM, NUM_PIXELS

__all__ = ['PIN_NUM', 'NUM_PIXELS']
