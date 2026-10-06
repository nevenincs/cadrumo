"""Validate COFF architecture independently of the PE32+ optional-header width."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from dev.packaging.native.platforms.pe import imports

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _pe(path: Path, machine: int) -> Path:
    image = bytearray(512)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", image, 0x84, machine)
    struct.pack_into("<H", image, 0x94, 240)
    struct.pack_into("<H", image, 0x98, 0x20B)
    path.write_bytes(image)
    return path


def test_amd64_pe_with_no_imports_is_admitted(tmp_path: Path) -> None:
    assert imports(_pe(tmp_path / "amd64.dll", 0x8664)) == set()


@pytest.mark.parametrize("machine", [0xAA64, 0x014C, 0])
def test_pe32_plus_does_not_admit_a_foreign_coff_machine(tmp_path: Path, machine: int) -> None:
    with pytest.raises(ValueError, match="AMD64 PE"):
        imports(_pe(tmp_path / "wrong.dll", machine))
