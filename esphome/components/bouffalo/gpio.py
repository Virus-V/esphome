"""GPIO support for Bouffalo Lab BL616CL targets."""

from __future__ import annotations

from typing import Any

from esphome import pins
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import (
    CONF_ID,
    CONF_INVERTED,
    CONF_MODE,
    CONF_NUMBER,
    CONF_OPEN_DRAIN,
    CONF_OUTPUT,
    CONF_PULLDOWN,
    CONF_PULLUP,
)
from esphome.core import CORE
from esphome.types import ConfigType

from .boards import BOARD_PINS
from .const import KEY_BOARD

bouffalo_ns = cg.esphome_ns.namespace("bouffalo")
BouffaloGPIOPin = bouffalo_ns.class_("BouffaloGPIOPin", cg.InternalGPIOPin)

# BL616CL exposes GPIO0..GPIO36. GPIO32 and GPIO33 are dedicated to USB on the
# currently supported Arduino variant and must not be claimed by ESPHome.
MAX_GPIO = 36
RESERVED_GPIO = {
    32: "USB D-",
    33: "USB D+",
}


def _current_board() -> str:
    return CORE.data["bouffalo"][KEY_BOARD]


def validate_pin(value: Any) -> int:
    """Resolve numerical and board-level pin aliases to a BL616CL GPIO number."""
    aliases = BOARD_PINS[_current_board()]
    if isinstance(value, str):
        if value in aliases:
            value = aliases[value]
        elif value.upper().startswith("GPIO"):
            value = value[4:]
        elif value.upper().startswith("P") and value[1:].isdigit():
            value = value[1:]

    try:
        number = cv.int_range(min=0, max=MAX_GPIO)(value)
    except cv.Invalid as err:
        raise cv.Invalid(
            f"BL616CL GPIO must be an alias or a number from 0 to {MAX_GPIO}"
        ) from err

    if reservation := RESERVED_GPIO.get(number):
        raise cv.Invalid(f"GPIO{number} is reserved for {reservation}")
    return number


def validate_mode(config: ConfigType) -> ConfigType:
    mode = config[CONF_MODE]
    if mode[CONF_OPEN_DRAIN] and not mode[CONF_OUTPUT]:
        raise cv.Invalid(
            "Open-drain mode requires an output", [CONF_MODE, CONF_OPEN_DRAIN]
        )
    if mode[CONF_PULLUP] and mode[CONF_PULLDOWN]:
        raise cv.Invalid(
            "A GPIO cannot enable pull-up and pull-down together", [CONF_MODE]
        )
    return config


PIN_SCHEMA = cv.All(
    pins.gpio_base_schema(
        BouffaloGPIOPin,
        validate_pin,
        modes=pins.GPIO_STANDARD_MODES,
    ),
    validate_mode,
)


@pins.PIN_SCHEMA_REGISTRY.register("bouffalo", PIN_SCHEMA)
async def pin_to_code(config: ConfigType) -> cg.MockObj:
    var = cg.new_Pvariable(config[CONF_ID])
    cg.add(var.set_pin(config[CONF_NUMBER]))
    if config[CONF_INVERTED]:
        cg.add(var.set_inverted(True))
    cg.add(var.set_flags(pins.gpio_flags_expr(config[CONF_MODE])))
    return var
