#!/usr/bin/env python3
"""Generate ESPHome board metadata from an arduino-bouffalo checkout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

_PIN_RE = re.compile(r"^\s*static const uint8_t (\w+) = ([^;]+);")
_DEFINE_RE = re.compile(r"^\s*#define (\w+) (\w+)")
_PIN_ALIASES = {
    "LED_BUILTIN": "LED_BUILTIN",
    "SDA": "SDA",
    "SCL": "SCL",
    "PIN_SERIAL_TX": "UART0_TX",
    "PIN_SERIAL_RX": "UART0_RX",
    "PIN_SERIAL1_TX": "UART1_TX",
    "PIN_SERIAL1_RX": "UART1_RX",
}


def _parse_properties(path: Path) -> dict[str, dict[str, str]]:
    boards: dict[str, dict[str, str]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        board_id, separator, property_name = key.partition(".")
        if not separator:
            continue
        boards.setdefault(board_id, {})[property_name] = value
    return boards


def _parse_pins(path: Path) -> dict[str, int]:
    raw: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if match := _PIN_RE.match(line):
            raw[match[1]] = match[2].strip()
        elif match := _DEFINE_RE.match(line):
            raw.setdefault(match[1], match[2].strip())

    resolved: dict[str, int] = {}
    for _ in range(len(raw) + 1):
        progress = False
        for name, expression in raw.items():
            if name in resolved:
                continue
            if expression.isdigit():
                resolved[name] = int(expression)
                progress = True
            elif expression in resolved:
                resolved[name] = resolved[expression]
                progress = True
        if not progress:
            break

    pins = {
        alias: resolved[source]
        for source, alias in _PIN_ALIASES.items()
        if source in resolved
    }
    return dict(sorted(pins.items()))


def _python_literal(value: object, indent: int = 0) -> str:
    """Render simple board metadata as deterministic, Ruff-compatible Python."""
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for key in sorted(value):
            rendered_key = json.dumps(key) if isinstance(key, str) else str(key)
            rendered_value = _python_literal(value[key], indent + 4)
            lines.append(f"{' ' * (indent + 4)}{rendered_key}: {rendered_value},")
        lines.append(f"{' ' * indent}}}")
        return "\n".join(lines)
    if isinstance(value, str):
        return json.dumps(value)
    return repr(value)


def generate(core: Path) -> str:
    properties = _parse_properties(core / "boards.txt")
    boards: dict[str, dict[str, object]] = {}
    board_pins: dict[str, dict[str, int]] = {}

    for board_id, values in sorted(properties.items()):
        if "build.mcu" not in values or "build.variant" not in values:
            continue
        mcu = values["build.mcu"]
        variant_dir = values["build.variant"]
        pins = _parse_pins(core / "variants" / variant_dir / "pins_arduino.h")
        board_pins[board_id] = pins
        boards[board_id] = {
            "name": values.get("name", board_id),
            "variant": mcu.upper(),
            "fqbn": f"bouffalo:{mcu}:{board_id}",
            "pins": board_id,
            "reserved_pins": {
                32: "USB D-",
                33: "USB D+",
            }
            if mcu == "bl616cl"
            else {},
        }

    if not boards:
        raise ValueError(f"No Bouffalo boards found in {core / 'boards.txt'}")

    return (
        '"""Board definitions for Bouffalo Lab Arduino targets."""\n\n'
        "from __future__ import annotations\n\n"
        f'DEFAULT_BOARD = "{next(iter(boards))}"\n\n'
        f"BOARD_PINS = {_python_literal(board_pins)}\n\n"
        f"BOARDS = {_python_literal(boards)}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--arduino-core",
        required=True,
        type=Path,
        help="Path to an arduino-bouffalo checkout",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("boards.py"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    content = generate(args.arduino_core.resolve())
    if args.check:
        if args.output.read_text(encoding="utf-8") != content:
            print(f"{args.output} is out of date; regenerate it", file=sys.stderr)
            return 1
        return 0

    args.output.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
