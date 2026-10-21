"""Reprovisioning the Windows CPython SDK rewrites only what the archive changed."""

from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path

import pytest

from ..platforms.windows import provision_sdk

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PIN = "3.13.11"
CONTRACT = {"sdk": {"root": "cpython-nuget/tools"}}
SOURCE = "https://api.nuget.org/v3-flatcontainer/python/{version}/python.{version}.nupkg"
OLD_NS = 1_600_000_000_000_000_000


def _archive(destination: Path, members: dict[str, bytes]) -> dict[str, str]:
    """Place the NuGet archive the backend would download, and name its digest."""
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"python.{PIN}.nupkg"
    with zipfile.ZipFile(archive, "w") as package:
        for name, content in members.items():
            package.writestr(name, content)
    return {"cpython_source": SOURCE, "cpython_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}


def test_reprovisioning_keeps_unchanged_files_rewrites_changed_ones_and_drops_stale_ones(tmp_path: Path) -> None:
    members = {"tools/include/Python.h": b"/* first */\n", "tools/libs/python313.lib": b"lib"}
    root = provision_sdk(tmp_path, PIN, _archive(tmp_path, members), CONTRACT)
    header, library = root / "include/Python.h", root / "libs/python313.lib"
    assert header.read_bytes() == b"/* first */\n" and library.read_bytes() == b"lib"
    for path in (header, library):
        os.utime(path, ns=(OLD_NS, OLD_NS))
    stale = root / "include/removed.h"
    stale.write_bytes(b"/* no longer in the archive */\n")

    changed = {**members, "tools/libs/python313.lib": b"changed lib"}
    (tmp_path / f"python.{PIN}.nupkg").unlink()
    provision_sdk(tmp_path, PIN, _archive(tmp_path, changed), CONTRACT)

    # Unchanged bytes keep their timestamp, so nothing compiled against them rebuilds.
    assert header.stat().st_mtime_ns == OLD_NS
    assert library.read_bytes() == b"changed lib" and library.stat().st_mtime_ns != OLD_NS
    assert not stale.exists()


def test_a_damaged_archive_is_refused_before_anything_is_extracted(tmp_path: Path) -> None:
    tools = _archive(tmp_path, {"tools/include/Python.h": b"/* first */\n"})
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        provision_sdk(tmp_path, PIN, {**tools, "cpython_sha256": "0" * 64}, CONTRACT)
    assert not (tmp_path / "cpython-nuget").exists()
