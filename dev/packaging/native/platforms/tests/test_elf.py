"""The ELF reader returns needed libraries and the highest glibc symbol version without loading the image."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.packaging.native.platforms.elf import read_elf_requirements
from dev.packaging.native.tests.binary_fixtures import elf_image, elf_with_requirements

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_needed_libraries_and_the_highest_glibc_version_are_read(tmp_path: Path) -> None:
    image = elf_with_requirements(
        tmp_path / "program",
        needed=("libggml.so.0", "libc.so.6"),
        glibc=("2.17", "2.34", "2.28"),
    )

    requirements = read_elf_requirements(image)

    assert requirements.needed == ("libggml.so.0", "libc.so.6")
    assert requirements.glibc == (2, 34)


def test_an_image_without_version_needs_requires_no_glibc(tmp_path: Path) -> None:
    requirements = read_elf_requirements(elf_with_requirements(tmp_path / "program", needed=("libm.so.6",)))

    assert requirements.glibc is None


def test_a_three_part_glibc_version_orders_after_its_two_part_prefix(tmp_path: Path) -> None:
    image = elf_with_requirements(tmp_path / "program", glibc=("2.2.5", "2.2"))

    assert read_elf_requirements(image).glibc == (2, 2, 5)


def test_a_header_without_section_headers_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no section headers"):
        read_elf_requirements(elf_image(tmp_path / "bare"))


def test_a_file_that_is_not_an_elf64_image_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "text"
    path.write_bytes(b"not an image" * 10)

    with pytest.raises(ValueError, match="ELF64"):
        read_elf_requirements(path)


def test_a_truncated_section_table_is_refused(tmp_path: Path) -> None:
    image = elf_with_requirements(tmp_path / "program", needed=("libc.so.6",), glibc=("2.34",))
    image.write_bytes(image.read_bytes()[:-40])

    with pytest.raises(ValueError, match="Truncated ELF"):
        read_elf_requirements(image)
