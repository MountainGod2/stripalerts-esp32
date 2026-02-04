"""
Manifest file for frozen modules in MicroPython firmware.
Modules listed here will be compiled into the firmware.

Note: This file is not used by the build system (tools/cli.py generates its own manifest).
It's kept here for reference or manual builds.
"""
include("$(PORT_DIR)/boards/manifest.py")

# Freeze the stripalerts package using recommended package() function
# Use absolute path since this is an external module outside the MicroPython tree
package("stripalerts", base_path="$(MPY_DIR)/../../../frozen", opt=3)
