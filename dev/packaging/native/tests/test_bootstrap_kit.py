"""Portable kit publication retains verified bytes and rejects changed sources."""

from pathlib import Path

import pytest

from ..hashing import digest
from ..windows_msi_build import _deliver_kit

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_delivery_keeps_identical_artifacts_and_publishes_descriptor_last(tmp_path: Path) -> None:
    source = tmp_path / "runner.exe"
    source.write_bytes(b"fixture runner bytes")
    directory = tmp_path / "services"
    directory.mkdir()
    descriptor = directory / "kit.json"
    sources = {source.name: (source, digest(source))}
    assert _deliver_kit(directory, descriptor, sources, "verified descriptor\n") == descriptor
    delivered = directory / source.name
    assert delivered.read_bytes() == source.read_bytes()
    stamp = delivered.stat().st_mtime_ns
    _deliver_kit(directory, descriptor, sources, "next descriptor\n")
    assert delivered.stat().st_mtime_ns == stamp
    assert descriptor.read_text(encoding="utf-8") == "next descriptor\n"
    assert sorted(path.name for path in directory.iterdir()) == ["kit.json", "runner.exe"]


def test_changed_source_preserves_last_descriptor_and_cleans_work(tmp_path: Path) -> None:
    source = tmp_path / "version.msi"
    source.write_bytes(b"admitted artifact")
    checksum = digest(source)
    source.write_bytes(b"changed artifact")
    directory = tmp_path / "services"
    directory.mkdir()
    descriptor = directory / "kit.json"
    descriptor.write_text("previous descriptor", encoding="utf-8")
    with pytest.raises(ValueError, match="source changed"):
        _deliver_kit(directory, descriptor, {source.name: (source, checksum)}, "replacement descriptor")
    assert descriptor.read_text(encoding="utf-8") == "previous descriptor"
    assert [path.name for path in directory.iterdir()] == ["kit.json"]
