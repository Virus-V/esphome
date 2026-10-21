"""Tests for the Bouffalo native build backend."""

from __future__ import annotations

import struct
import zlib

import pytest

from esphome.bouffalo import toolchain
from esphome.core import EsphomeError


def _partition_table() -> bytes:
    header = bytearray(16)
    header[:4] = b"BFPT"
    struct.pack_into("<H", header, 6, 1)
    struct.pack_into("<I", header, 12, zlib.crc32(header[:12]))

    entry = struct.pack(
        "<BBB9sIIIIII",
        1,
        0,
        0,
        b"FW",
        0x10000,
        0x1C4000,
        toolchain.OTA_SLOT_SIZE,
        toolchain.OTA_SLOT_SIZE,
        0,
        0,
    )
    return bytes(header) + entry + struct.pack("<I", zlib.crc32(entry))


def test_make_factory_image_layout() -> None:
    boot2 = b"BFNP" + bytes(32)
    partition = _partition_table()
    payload = b"BFNP" + bytes(64)

    image = toolchain.make_factory_image(boot2, partition, payload)

    assert image[: len(boot2)] == boot2
    assert image[0xE000 : 0xE000 + len(partition)] == partition
    assert image[0xF000 : 0xF000 + len(partition)] == partition
    assert image[0x10000:] == payload


def test_make_factory_image_rejects_bad_boot2() -> None:
    with pytest.raises(EsphomeError, match="boot2"):
        toolchain.make_factory_image(
            b"not-boot2", _partition_table(), b"BFNP" + bytes(64)
        )


def test_make_factory_image_rejects_oversized_payload() -> None:
    with pytest.raises(EsphomeError, match="application slot"):
        toolchain.make_factory_image(
            b"BFNP" + bytes(32),
            _partition_table(),
            b"X" * (toolchain.OTA_SLOT_SIZE + 1),
        )


def test_make_factory_image_rejects_bad_table_crc() -> None:
    partition = bytearray(_partition_table())
    partition[-1] ^= 0xFF
    with pytest.raises(EsphomeError, match="CRC"):
        toolchain.make_factory_image(
            b"BFNP" + bytes(32), bytes(partition), b"BFNP" + bytes(64)
        )
