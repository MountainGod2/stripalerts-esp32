#define MICROPY_HW_BOARD_NAME               "StripAlerts MCU"
#define MICROPY_HW_MCU_NAME                 "ESP32"

// Enable UART REPL for modules that have an external USB-UART and don't use native USB.
#define MICROPY_HW_ENABLE_UART_REPL         (1)

#define MICROPY_HW_I2C0_SCL                 (9)
#define MICROPY_HW_I2C0_SDA                 (8)
