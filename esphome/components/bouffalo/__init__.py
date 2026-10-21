"""Bouffalo Lab Arduino platform."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import time
from typing import Any

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import (
    CONF_AP,
    CONF_BAUD_RATE,
    CONF_BOARD,
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
    KEY_CORE,
    KEY_FRAMEWORK_VERSION,
    KEY_TARGET_FRAMEWORK,
    KEY_TARGET_PLATFORM,
    PLATFORM_BOUFFALO,
    ThreadModel,
    Toolchain,
)
from esphome.core import CORE, EsphomeError
import esphome.final_validate as fv
from esphome.storage_json import StorageJSON
from esphome.types import ConfigType

from . import gpio  # noqa: F401  # Register the pin schema.
from .boards import BOARDS, DEFAULT_BOARD
from .const import KEY_BOARD, KEY_FQBN, KEY_VARIANT

_LOGGER = logging.getLogger(__name__)
CODEOWNERS = ["@Virus-V"]
AUTO_LOAD = ["preferences"]
DOMAIN = "bouffalo"
IS_TARGET_PLATFORM = True

CONF_ARDUINO_CLI_CONFIG = "arduino_cli_config"
CONF_ARDUINO_CORE_PATH = "arduino_core_path"
CONF_PASSIVE_SCAN = "passive_scan"

# The Arduino core does not expose semantic release numbers yet. Keep this in
# one place so generated version checks can be updated with the first release.
ARDUINO_CORE_VERSION = cv.Version(0, 1, 0)


def _set_core_data(config: ConfigType) -> ConfigType:
    board = config[CONF_BOARD]
    board_info = BOARDS[board]
    CORE.data[DOMAIN] = dict(config)
    CORE.data[KEY_CORE][KEY_TARGET_PLATFORM] = PLATFORM_BOUFFALO
    CORE.data[KEY_CORE][KEY_TARGET_FRAMEWORK] = "arduino"
    CORE.data[KEY_CORE][KEY_FRAMEWORK_VERSION] = ARDUINO_CORE_VERSION
    CORE.data[DOMAIN][KEY_BOARD] = board
    CORE.data[DOMAIN][KEY_FQBN] = board_info["fqbn"]
    CORE.data[DOMAIN][KEY_VARIANT] = board_info["variant"]
    return config


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.Optional(CONF_BOARD, default=DEFAULT_BOARD): cv.one_of(
                *BOARDS, lower=True
            ),
            cv.Optional(CONF_ARDUINO_CORE_PATH): cv.directory,
            cv.Optional(CONF_ARDUINO_CLI_CONFIG): cv.file_,
        }
    ),
    cv.resolve_toolchain("Bouffalo", (Toolchain.BOUFFALO,), Toolchain.BOUFFALO),
    _set_core_data,
)


def _final_validate(_: ConfigType) -> None:
    full_config = fv.full_config.get()

    for index, ota_config in enumerate(full_config.get(CONF_OTA, [])):
        if ota_config.get(CONF_PLATFORM) == CONF_ESPHOME:
            raise cv.FinalExternalInvalid(
                "ESPHome network OTA is not supported on Bouffalo yet; use UART flashing",
                path=[CONF_OTA, index, CONF_PLATFORM],
            )

    if (mdns_config := full_config.get(CONF_MDNS)) is not None and not mdns_config.get(
        CONF_DISABLED
    ):
        raise cv.FinalExternalInvalid(
            "mDNS is not supported on Bouffalo yet because its lwIP netif "
            "does not support IGMP multicast membership",
            path=[CONF_MDNS, CONF_DISABLED],
        )

    if (wifi_config := full_config.get(CONF_WIFI)) is None:
        return
    if CONF_AP in wifi_config:
        raise cv.FinalExternalInvalid(
            "Bouffalo currently supports Wi-Fi station mode only",
            path=[CONF_WIFI, CONF_AP],
        )
    if CONF_EAP in wifi_config:
        raise cv.FinalExternalInvalid(
            "Bouffalo WPA2 Enterprise is not implemented",
            path=[CONF_WIFI, CONF_EAP],
        )
    for index, network in enumerate(wifi_config.get(CONF_NETWORKS, [])):
        if CONF_EAP in network:
            raise cv.FinalExternalInvalid(
                "Bouffalo WPA2 Enterprise is not implemented",
                path=[CONF_WIFI, CONF_NETWORKS, index, CONF_EAP],
            )
    if wifi_config[CONF_POWER_SAVE_MODE] != "NONE":
        raise cv.FinalExternalInvalid(
            "Bouffalo Wi-Fi power saving is not implemented",
            path=[CONF_WIFI, CONF_POWER_SAVE_MODE],
        )
    if CONF_OUTPUT_POWER in wifi_config:
        raise cv.FinalExternalInvalid(
            "Bouffalo Wi-Fi output power control is not implemented",
            path=[CONF_WIFI, CONF_OUTPUT_POWER],
        )
    if wifi_config[CONF_PASSIVE_SCAN]:
        raise cv.FinalExternalInvalid(
            "Bouffalo passive scanning is not implemented",
            path=[CONF_WIFI, CONF_PASSIVE_SCAN],
        )


FINAL_VALIDATE_SCHEMA = _final_validate


def get_board() -> str:
    """Return the board identifier selected for the current configuration."""
    return CORE.data[DOMAIN][KEY_BOARD]


def get_board_info() -> dict[str, Any]:
    """Return the board metadata selected for the current configuration."""
    return BOARDS[get_board()]


def get_fqbn() -> str:
    """Return the Arduino FQBN for the current build."""
    return CORE.data[DOMAIN][KEY_FQBN]


def get_core_path(config: ConfigType | None = None) -> Path | None:
    """Return an explicitly configured Arduino core checkout, if any."""
    if config is not None and (path := config.get(CONF_ARDUINO_CORE_PATH)):
        return Path(path).expanduser().resolve()
    if (path := CORE.data.get(DOMAIN, {}).get(CONF_ARDUINO_CORE_PATH)) is not None:
        return Path(path).expanduser().resolve()
    return None


def get_cli_config(config: ConfigType | None = None) -> Path | None:
    """Return an explicitly configured arduino-cli config file, if any."""
    if config is not None and (path := config.get(CONF_ARDUINO_CLI_CONFIG)):
        return Path(path).expanduser().resolve()
    if (path := CORE.data.get(DOMAIN, {}).get(CONF_ARDUINO_CLI_CONFIG)) is not None:
        return Path(path).expanduser().resolve()
    return None


def get_download_types(storage_json: StorageJSON) -> list[dict[str, str]]:
    """Return firmware images exposed by the dashboard download panel."""
    if storage_json.firmware_bin_path is None:
        return []
    return [
        {
            "title": "Factory image",
            "description": "For first-time flashing over UART at address 0x0.",
            "file": "firmware.factory.bin",
            "download": f"{storage_json.name}.factory.bin",
        },
    ]


async def to_code(config: ConfigType) -> None:
    board = config[CONF_BOARD]
    board_info = BOARDS[board]

    cg.add_build_flag("-DUSE_BOUFFALO")
    cg.add_build_flag("-DUSE_ARDUINO")
    cg.add_define(
        "USE_ARDUINO_VERSION_CODE",
        cg.RawExpression(
            f"VERSION_CODE({ARDUINO_CORE_VERSION.major}, "
            f"{ARDUINO_CORE_VERSION.minor}, {ARDUINO_CORE_VERSION.patch})"
        ),
    )
    cg.add_define("USE_NATIVE_64BIT_TIME")
    cg.add_define("USE_PREFERENCE_KEY_LOOKUP")
    cg.add_define("ESPHOME_BOARD", board)
    cg.add_define("ESPHOME_VARIANT", board_info["variant"])
    cg.add_define("ESPHOME_MANUFACTURER", "Bouffalo Lab")
    cg.add_define(ThreadModel.MULTI_NO_ATOMICS)
    cg.set_cpp_standard("gnu++20")


def run_compile(args: object, config: ConfigType) -> bool:
    """Build through the native arduino-cli backend."""
    from esphome.bouffalo import toolchain

    if toolchain.run_compile(config, CORE.verbose) != 0:
        raise EsphomeError("Bouffalo build failed")
    return True


def upload_program(config: ConfigType, args: object, host: str) -> bool:
    """Flash the combined factory image over UART."""
    from esphome.__main__ import check_permissions
    from esphome.bouffalo import toolchain
    from esphome.upload_targets import PortType, get_port_type

    if get_port_type(host) != PortType.SERIAL:
        return False
    check_permissions(host)
    # The upload fast path may use a validated-config cache without running
    # component validators, so restore the derived board metadata first.
    if KEY_FQBN not in CORE.data.get(DOMAIN, {}):
        _set_core_data(config[DOMAIN])
    else:
        CORE.data.setdefault(DOMAIN, dict(config[DOMAIN]))
    if toolchain.upload(host, getattr(args, "file", None)) != 0:
        raise EsphomeError("Bouffalo serial upload failed")
    return True


def show_logs(config: ConfigType, args: object, devices: list[str]) -> bool:
    """Stream logs over UART with BL616CL-safe modem-control levels."""
    from aioesphomeapi import LogParser
    import serial

    from esphome.__main__ import (
        SERIAL_BUFFER_MAX_SIZE,
        _wait_for_serial_port,
        check_permissions,
    )
    from esphome.upload_targets import PortType, get_port_type
    from esphome.util import safe_print

    port = devices[0]
    if get_port_type(port) != PortType.SERIAL:
        return False
    if "logger" not in config:
        raise EsphomeError("Logger is not configured!")
    baud_rate = config["logger"][CONF_BAUD_RATE]
    if baud_rate == 0:
        raise EsphomeError("UART logging is disabled (baud_rate=0)")

    _wait_for_serial_port(port)
    check_permissions(port)
    _LOGGER.info("Starting log output from %s with baud rate %s", port, baud_rate)
    connection = serial.Serial()
    connection.port = port
    connection.baudrate = baud_rate
    # The UNO R4 BL616CL carrier uses DTR for BOOT and RTS for CHIP_EN. Both
    # default to asserted, which holds the SoC in reset instead of running the
    # application and streaming its log.
    connection.dtr = True
    connection.rts = False
    parser = LogParser()
    buffer = b""
    try:
        with connection:
            connection.timeout = 0.1
            if getattr(args, "reset", False):
                connection.rts = True
                time.sleep(0.1)
                connection.rts = False
            while True:
                chunk = connection.read(connection.in_waiting or 1)
                if not chunk:
                    continue
                now = datetime.now().astimezone()
                time_str = (
                    f"[{now.hour:02}:{now.minute:02}:{now.second:02}."
                    f"{now.microsecond // 1000:03}]"
                )
                buffer += chunk
                if len(buffer) > SERIAL_BUFFER_MAX_SIZE:
                    buffer = buffer[-SERIAL_BUFFER_MAX_SIZE:]
                while b"\n" in buffer:
                    raw_line, buffer = buffer.split(b"\n", 1)
                    line = raw_line.replace(b"\r", b"").decode(
                        "utf8", "backslashreplace"
                    )
                    safe_print(parser.parse_line(line, time_str))
    except KeyboardInterrupt:
        return True
    except serial.SerialException as err:
        raise EsphomeError(f"Serial port closed: {err}") from err
