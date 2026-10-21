"""Tests for the Bouffalo target platform configuration."""

from __future__ import annotations

import pytest

from esphome.components import bouffalo, wifi
from esphome.components.bouffalo import gpio
from esphome.config_validation import Invalid
from esphome.const import PLATFORM_BOUFFALO, Toolchain
from esphome.core import CORE


@pytest.fixture(autouse=True)
def bouffalo_core():
    """Populate the minimum CORE data needed by pin validation."""
    CORE.data["bouffalo"] = {"board": bouffalo.DEFAULT_BOARD}
    yield
    CORE.data.pop("bouffalo", None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5, 5),
        ("5", 5),
        ("GPIO5", 5),
        ("P5", 5),
        ("LED_BUILTIN", 31),
        ("SDA", 11),
        ("SCL", 14),
    ],
)
def test_validate_pin(value: str | int, expected: int) -> None:
    assert gpio.validate_pin(value) == expected


@pytest.mark.parametrize("value", [-1, 37, "GPIO37", "not-a-pin"])
def test_validate_pin_rejects_out_of_range(value: str | int) -> None:
    with pytest.raises(Invalid):
        gpio.validate_pin(value)


@pytest.mark.parametrize(("value", "purpose"), [(32, "USB D-"), (33, "USB D+")])
def test_validate_pin_rejects_usb_pins(value: int, purpose: str) -> None:
    with pytest.raises(Invalid, match=purpose):
        gpio.validate_pin(value)


def test_board_definition() -> None:
    board = bouffalo.BOARDS["unor4_bl616cl"]
    assert board["variant"] == "BL616CL"
    assert board["fqbn"] == "bouffalo:bl616cl:unor4_bl616cl"


def test_bouffalo_has_native_wifi() -> None:
    assert wifi.has_native_wifi(platform=PLATFORM_BOUFFALO)


def test_bouffalo_is_a_native_toolchain() -> None:
    from esphome.build_helpers.native import NATIVE_TOOLCHAIN_MODULES
    from esphome.const import NATIVE_TOOLCHAINS

    assert Toolchain.BOUFFALO in NATIVE_TOOLCHAINS
    assert (
        NATIVE_TOOLCHAIN_MODULES[(PLATFORM_BOUFFALO, Toolchain.BOUFFALO)]
        == "esphome.bouffalo.toolchain"
    )
