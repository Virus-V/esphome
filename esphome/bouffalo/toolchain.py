"""Native Arduino CLI build backend for Bouffalo Lab targets."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import zlib

from esphome.build_helpers.native import warn_ignored_platformio_options
from esphome.core import CORE, EsphomeError
from esphome.types import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "bouffalo"
BOARD_STAGE_PARTITION = "partition_cfg_esphome_4M.toml"
OTA_SLOT_SIZE = 0x1B4000
CONF_ARDUINO_CLI_CONFIG = "arduino_cli_config"
CONF_ARDUINO_CORE_PATH = "arduino_core_path"

# Native toolchains have no platformio.ini options to consume.
_NATIVE_CONSUMED_PIO_OPTIONS: frozenset[str] = frozenset()


def get_build_dir() -> Path:
    return CORE.relative_pioenvs_path(CORE.name)


def get_elf_path() -> Path:
    return get_build_dir() / "firmware.elf"


def get_factory_firmware_path() -> Path:
    return get_build_dir() / "firmware.factory.bin"


def missing_image_hint() -> str:
    return "Compile the configuration before uploading"


def _cli(config: ConfigType | None = None) -> list[str]:
    executable = shutil.which("arduino-cli")
    if executable is None:
        raise EsphomeError(
            "arduino-cli was not found in PATH. Install it before compiling "
            "a Bouffalo target."
        )
    command = [executable]
    cli_config = (
        config.get(CONF_ARDUINO_CLI_CONFIG)
        if config is not None
        else CORE.data.get(DOMAIN, {}).get(CONF_ARDUINO_CLI_CONFIG)
    )
    cli_config = cli_config or os.getenv("ESPHOME_ARDUINO_CLI_CONFIG")
    if cli_config:
        command.extend(["--config-file", str(cli_config)])
    return command


def _explicit_core_path(config: ConfigType | None) -> Path | None:
    value = (
        config.get(CONF_ARDUINO_CORE_PATH)
        if config is not None
        else CORE.data.get(DOMAIN, {}).get(CONF_ARDUINO_CORE_PATH)
    )
    return Path(value).expanduser().resolve() if value else None


def get_core_path(config: ConfigType | None = None) -> Path:
    """Resolve the installed Arduino platform containing the BL616CL core.

    An explicit ``arduino_core_path`` is verified against arduino-cli. When it
    is omitted, the path is read from the installed platform's build
    properties so the normal configuration does not contain machine paths.
    """
    if cached := CORE.data.get(DOMAIN, {}).get("_core_path"):
        return Path(cached)

    fqbn = CORE.data[DOMAIN]["fqbn"]
    details = subprocess.run(
        _cli(config) + ["board", "details", "--fqbn", fqbn, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if details.returncode:
        raise EsphomeError(
            "The Bouffalo Arduino platform is not registered with arduino-cli. "
            "Install the arduino-bouffalo platform first.\n"
            f"arduino-cli: {details.stderr.strip()}"
        )
    properties = json.loads(details.stdout).get("build_properties", [])
    detected = next(
        (
            item.partition("=")[2]
            for item in properties
            if item.startswith("runtime.platform.path=")
        ),
        "",
    )
    if not detected:
        raise EsphomeError("arduino-cli did not report runtime.platform.path")
    core = Path(detected).expanduser().resolve()
    if explicit := _explicit_core_path(config):
        if explicit != core:
            raise EsphomeError(
                f"arduino_core_path is {explicit}, but arduino-cli uses {core}; "
                "register that checkout instead"
            )
        core = explicit
    CORE.data.setdefault(DOMAIN, {})["_core_path"] = str(core)
    return core


def _tool(name: str) -> Path:
    return get_core_path() / "tools/Xuantie-900-gcc/bin" / f"riscv64-unknown-elf-{name}"


def get_objdump_path() -> Path:
    return _tool("objdump")


def get_readelf_path() -> Path:
    return _tool("readelf")


def get_addr2line_path() -> Path:
    return _tool("addr2line")


def _stage_libraries(destination: Path, compiled_src: Path) -> list[str]:
    """Stage PlatformIO-resolved libraries where Arduino CLI can compile them."""
    from platformio import fs
    from platformio.package.manager.library import LibraryPackageManager

    cache = CORE.relative_build_path("library-cache")
    cache.mkdir(parents=True, exist_ok=True)
    manager = LibraryPackageManager(str(cache))
    flags: list[str] = []
    for library in CORE.platformio_libraries.values():
        if library.version is None and library.repository is None:
            continue  # Arduino CLI resolves installed framework libraries.
        package = manager.install(library.as_lib_dep)
        source = Path(package.path).resolve()
        manifest_path = source / "library.json"
        if not manifest_path.is_file():
            raise EsphomeError(f"Bouffalo requires library.json for {library}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        settings = manifest.get("build", {})
        if settings.get("extraScript"):
            raise EsphomeError(
                f"Bouffalo cannot run PlatformIO build scripts for {library}"
            )
        name = manifest["name"]
        target = destination / name
        shutil.copytree(source, target)
        source_dir = source / settings.get("srcDir", "src")
        selected = {
            (source_dir / item).resolve()
            for item in fs.match_src_files(
                str(source_dir), settings.get("srcFilter", "+<*>")
            )
        }
        for item in target.rglob("*"):
            if (
                item.suffix in {".c", ".cpp", ".cc", ".S", ".s"}
                and (source / item.relative_to(target)).resolve() not in selected
            ):
                item.unlink()
        include_dir = (
            compiled_src / "dependencies" / name / settings.get("includeDir", "include")
        )
        source_include = (
            compiled_src / "dependencies" / name / settings.get("srcDir", "src")
        )
        flags.extend([f"-I{include_dir}", f"-I{source_include}"])
        library_flags = settings.get("flags", [])
        tokens = shlex.split(
            library_flags if isinstance(library_flags, str) else " ".join(library_flags)
        )
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == "-I":
                index += 1
                flags.append(f"-I{target / tokens[index]}")
            elif token.startswith("-I"):
                flags.append(f"-I{target / token[2:]}")
            else:
                flags.append(token)
            index += 1
    return flags


def run_compile(config: ConfigType, verbose: bool) -> int:
    """Compile ESPHome's generated sketch through the Arduino CLI."""
    core = get_core_path(config)
    if not (core / "cores/bl616cl/Arduino.h").is_file():
        raise EsphomeError(f"Not a BL616CL Arduino core: {core}")

    warn_ignored_platformio_options(_NATIVE_CONSUMED_PIO_OPTIONS)
    build = get_build_dir()
    build.mkdir(parents=True, exist_ok=True)
    sketch = CORE.relative_build_path("arduino", "firmware")
    sketch.mkdir(parents=True, exist_ok=True)
    (sketch / "firmware.ino").write_text(
        "// ESPHome generates setup() and loop() in src/main.cpp.\n",
        encoding="utf-8",
    )
    staged_src = sketch / "src"
    if staged_src.exists():
        shutil.rmtree(staged_src)
    shutil.copytree(CORE.relative_src_path(), staged_src)
    compiled_src = build / "sketch/src"
    dependencies = staged_src / "dependencies"
    dependencies.mkdir()
    flags = ["-DUSE_BOUFFALO", f"-I{compiled_src}"]
    flags.extend(sorted(CORE.build_flags))
    flags.extend(_stage_libraries(dependencies, compiled_src))

    command = _cli(config) + [
        "compile",
        "--fqbn",
        CORE.data[DOMAIN]["fqbn"],
        "--build-path",
        str(build),
        "--libraries",
        str(core / "libraries"),
        "--build-property",
        f"build.partition_config={BOARD_STAGE_PARTITION}",
        "--build-property",
        f"upload.maximum_size={OTA_SLOT_SIZE}",
        "--build-property",
        f"compiler.cpp.extra_flags={shlex.join(['-std=gnu++20', *flags])}",
        "--build-property",
        f"compiler.c.extra_flags={shlex.join(flags)}",
    ]
    if verbose:
        command.append("--verbose")
    command.append(str(sketch))
    _LOGGER.info("Building BL616CL using Arduino CLI")
    result = subprocess.run(command, check=False)
    if result.returncode:
        return result.returncode

    shutil.copy2(build / "firmware.ino.elf", get_elf_path())
    payload = (build / "firmware.ino.bin").read_bytes()
    (build / "firmware.bin").write_bytes(payload)
    boot2 = (build / "firmware.ino.boot2.bin").read_bytes()
    partition = (build / "firmware.ino.partition.bin").read_bytes()
    get_factory_firmware_path().write_bytes(
        make_factory_image(boot2, partition, payload)
    )
    return 0


def make_factory_image(boot2: bytes, partition: bytes, payload: bytes) -> bytes:
    """Combine boot2, partition tables and the application for UART flashing."""
    if not boot2.startswith(b"BFNP") or len(boot2) > 0xE000:
        raise EsphomeError("Invalid boot2 image")
    if not partition.startswith(b"BFPT") or not 20 <= len(partition) <= 4096:
        raise EsphomeError("Invalid partition table")
    if len(payload) > OTA_SLOT_SIZE:
        raise EsphomeError("Firmware exceeds the ESPHome application slot")
    count = struct.unpack_from("<H", partition, 6)[0]
    entries_end = 16 + 36 * count
    if (
        len(partition) != entries_end + 4
        or zlib.crc32(partition[:12]) != struct.unpack_from("<I", partition, 12)[0]
    ):
        raise EsphomeError("Invalid partition table length or header CRC")
    if (
        zlib.crc32(partition[16:entries_end])
        != struct.unpack_from("<I", partition, entries_end)[0]
    ):
        raise EsphomeError("Invalid partition entries CRC")
    entries = [
        struct.unpack_from("<BBB9sIIIIII", partition, 16 + 36 * i) for i in range(count)
    ]
    firmware = next(
        (entry for entry in entries if entry[3].rstrip(b"\0") == b"FW"), None
    )
    if (
        firmware is None
        or firmware[2] != 0
        or firmware[4:8] != (0x10000, 0x1C4000, OTA_SLOT_SIZE, OTA_SLOT_SIZE)
    ):
        raise EsphomeError(
            "Expected the dedicated ESPHome partition profile with slot 0 active"
        )
    for entry in entries:
        if entry is firmware:
            continue
        for address, size in zip(entry[4:6], entry[6:8], strict=True):
            if size and address < 0x378000 and address + size > 0x10000:
                raise EsphomeError("A partition overlaps an OTA firmware slot")
    image = bytearray(b"\xff" * (0x10000 + len(payload)))
    image[: len(boot2)] = boot2
    for offset in (0xE000, 0xF000):
        image[offset : offset + len(partition)] = partition
    image[0x10000:] = payload
    return bytes(image)


def upload(port: str, file: str | None = None) -> int:
    """Flash the combined factory image through Bouffalo FlashCube."""
    core = get_core_path()
    binary = Path(file) if file else get_factory_firmware_path()
    if not binary.is_file():
        raise EsphomeError(f"{missing_image_hint()}: {binary} is missing")
    image = binary.read_bytes()
    if image[0xE000:0xE004] != b"BFPT" or image[0x10000:0x10004] != b"BFNP":
        raise EsphomeError("Serial upload requires a combined factory image")
    if sys.platform == "win32":
        tool = core / "tools/bouffalo_flash_cube/BLFlashCommand.exe"
    else:
        suffix = "macos" if sys.platform == "darwin" else "ubuntu"
        tool = core / f"tools/bouffalo_flash_cube/BLFlashCommand-{suffix}"
    return subprocess.run(
        [
            str(tool),
            "--interface=uart",
            "--chipname=bl616cl",
            f"--port={port}",
            "--baudrate=2000000",
            f"--firmware={binary}",
        ],
        check=False,
    ).returncode


def get_idedata() -> dict | None:
    """Return IDE-style data derived from Arduino CLI's compile database."""
    from esphome.build_helpers.idedata import load_or_build_idedata

    return load_or_build_idedata(
        get_build_dir() / "compile_commands.json",
        get_elf_path(),
        CORE.relative_internal_path("idedata", f"{CORE.name}.bouffalo.json"),
        launcher=None,
    )
