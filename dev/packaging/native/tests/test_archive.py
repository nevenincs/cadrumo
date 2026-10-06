"""Portable bundle extraction refuses ambiguous paths and non-file payloads."""

from __future__ import annotations

import os
import stat
import zipfile
from pathlib import Path

import pytest

from ..archive import extract_bundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "member", ["../outside", "app/../outside", "app\\outside", "/absolute", "app/a:stream", "app/./alias"]
)
def test_invalid_paths_are_refused_before_extraction(tmp_path: Path, member: str) -> None:
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("app/valid", b"valid")
        entry = zipfile.ZipInfo("placeholder")
        entry.filename = member
        output.writestr(entry, b"invalid")
    destination = tmp_path / "extracted"
    with pytest.raises(ValueError, match="bundle member"):
        extract_bundle(archive, destination)
    assert not destination.exists()


def test_symlinks_are_refused(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    entry = zipfile.ZipInfo("app/link")
    entry.create_system = 3
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(entry, "../../outside")
    with pytest.raises(ValueError, match="link or special"):
        extract_bundle(archive, tmp_path / "extracted")


def test_case_aliases_are_refused(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("app/Python", b"first")
        output.writestr("app/python", b"second")
    with pytest.raises(ValueError, match="duplicate"):
        extract_bundle(archive, tmp_path / "extracted")


def test_regular_file_bytes_and_unix_executable_permissions(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    entry = zipfile.ZipInfo("app/python")
    entry.create_system = 3
    entry.external_attr = (stat.S_IFREG | 0o755) << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(entry, b"image")
    destination = tmp_path / "extracted"
    extract_bundle(archive, destination)
    executable = destination / "app/python"
    assert executable.read_bytes() == b"image"
    if os.name == "posix":
        assert stat.S_IMODE(executable.stat().st_mode) == 0o755
