"""Board definitions for Bouffalo Lab Arduino targets."""

from __future__ import annotations

DEFAULT_BOARD = "unor4_bl616cl"

BOARD_PINS = {
    "unor4_bl616cl": {
        "LED_BUILTIN": 31,
        "SCL": 14,
        "SDA": 11,
        "UART0_RX": 35,
        "UART0_TX": 34,
        "UART1_RX": 7,
        "UART1_TX": 6,
    },
}

BOARDS = {
    "unor4_bl616cl": {
        "fqbn": "bouffalo:bl616cl:unor4_bl616cl",
        "name": "UNO R4 WiFi BL616CL (Stage 1)",
        "pins": "unor4_bl616cl",
        "reserved_pins": {
            32: "USB D-",
            33: "USB D+",
        },
        "variant": "BL616CL",
    },
}
