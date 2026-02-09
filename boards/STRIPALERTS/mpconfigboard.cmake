set(IDF_TARGET esp32)

set(MICROPY_FROZEN_MANIFEST ${MICROPY_BOARD_DIR}/manifest.py)

set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.ble
    ${MICROPY_BOARD_DIR}/sdkconfig.board
)
