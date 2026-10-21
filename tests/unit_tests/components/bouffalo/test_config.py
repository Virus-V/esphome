"""Tests for the Bouffalo target platform configuration."""

from __future__ import annotations

import pytest

from esphome import final_validate as fv
from esphome.components import bouffalo, wifi
from esphome.components.bouffalo import gpio
from esphome.config_validation import FinalExternalInvalid, Invalid
from esphome.const import (
    CONF_AP,
    CONF_DISABLED,
    CONF_EAP,
    CONF_ESPHOME,
    CONF_MDNS,
    CONF_NETWORKS,
    CONF_OTA,
    CONF_OUTPUT_POWER,
    CONF_PLATFORM,
    CONF_POWER_SAVE_MODE,
    CONF_WIFI,
    PLATFORM_BOUFFALO,
    Toolchain,
)
from esphome.core import CORE
from esphome.types import ConfigType


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


def _run_final_validate(full_config: ConfigType) -> None:
    token = fv.full_config.set(full_config)
    try:
        bouffalo._final_validate({})
    finally:
        fv.full_config.reset(token)


def test_rejects_esphome_ota() -> None:
    with pytest.raises(
        FinalExternalInvalid,
        match="ESPHome network OTA is not supported on Bouffalo",
    ) as exc_info:
        _run_final_validate({CONF_OTA: [{CONF_PLATFORM: CONF_ESPHOME}]})

    assert exc_info.value.path == [CONF_OTA, 0, CONF_PLATFORM]


def test_allows_other_ota_platforms() -> None:
    _run_final_validate({CONF_OTA: [{CONF_PLATFORM: "web_server"}]})


def test_rejects_enabled_mdns() -> None:
    with pytest.raises(
        FinalExternalInvalid,
        match="mDNS is not supported on Bouffalo",
    ) as exc_info:
        _run_final_validate({CONF_MDNS: {CONF_DISABLED: False}})

    assert exc_info.value.path == [CONF_MDNS, CONF_DISABLED]


def test_allows_disabled_mdns() -> None:
    _run_final_validate({CONF_MDNS: {CONF_DISABLED: True}})


@pytest.mark.parametrize(
    ("wifi_config", "message", "path"),
    [
        (
            {CONF_AP: {}},
            "Bouffalo currently supports Wi-Fi station mode only",
            [CONF_WIFI, CONF_AP],
        ),
        (
            {CONF_EAP: {}},
            "Bouffalo WPA2 Enterprise is not implemented",
            [CONF_WIFI, CONF_EAP],
        ),
        (
            {CONF_NETWORKS: [{CONF_EAP: {}}]},
            "Bouffalo WPA2 Enterprise is not implemented",
            [CONF_WIFI, CONF_NETWORKS, 0, CONF_EAP],
        ),
        (
            {CONF_POWER_SAVE_MODE: "LIGHT"},
            "Bouffalo Wi-Fi power saving is not implemented",
            [CONF_WIFI, CONF_POWER_SAVE_MODE],
        ),
        (
            {CONF_OUTPUT_POWER: 20.0},
            "Bouffalo Wi-Fi output power control is not implemented",
            [CONF_WIFI, CONF_OUTPUT_POWER],
        ),
        (
            {wifi.CONF_PASSIVE_SCAN: True},
            "Bouffalo passive scanning is not implemented",
            [CONF_WIFI, wifi.CONF_PASSIVE_SCAN],
        ),
    ],
)
def test_rejects_unsupported_wifi_features(
    wifi_config: ConfigType, message: str, path: list[str | int]
) -> None:
    full_wifi = {
        CONF_POWER_SAVE_MODE: "NONE",
        wifi.CONF_PASSIVE_SCAN: False,
        **wifi_config,
    }

    with pytest.raises(FinalExternalInvalid, match=message) as exc_info:
        _run_final_validate({CONF_WIFI: full_wifi})

    assert exc_info.value.path == path


def test_allows_supported_wifi_config() -> None:
    _run_final_validate(
        {
            CONF_WIFI: {
                CONF_POWER_SAVE_MODE: "NONE",
                wifi.CONF_PASSIVE_SCAN: False,
            }
        }
    )
