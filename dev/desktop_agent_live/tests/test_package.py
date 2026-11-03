"""The lane's package mirrors the staged package with the test host as its admitted desktop image."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from cadrumo.core.hashing import canonical_json_bytes, sha256_hex

from ...packaging.native.layout import desktop_image, load_layout
from ..package import mirror, stage_lane_package

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _stage(root: Path, layout: dict[str, Any]) -> None:
    """Write a minimal staged package whose manifest and descriptors bind its own desktop image."""
    image = desktop_image(layout)
    assert image is not None
    files: dict[str, bytes] = {image.package_path: b"shipped desktop", "lib/module.py": b"print('payload')\n"}
    shipped = {"launch_image": image.package_path, "image_digest": _sha(files[image.package_path])}
    descriptor: dict[str, Any] = {"service_id": "desktop-session", **shipped, "allowed_parent_images": [shipped]}
    descriptor["descriptor_digest"] = sha256_hex(canonical_json_bytes(descriptor))
    files[layout["files"]["service_descriptors"]] = canonical_json_bytes([descriptor])
    manifest = {"layout": layout, "files": {member: _sha(content) for member, content in files.items()}}
    files[layout["files"]["package_manifest"]] = json.dumps(manifest, indent=2).encode("utf-8")
    for member, content in files.items():
        (root / member).parent.mkdir(parents=True, exist_ok=True)
        (root / member).write_bytes(content)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_the_mirror_runs_the_host_as_the_admitted_desktop_and_leaves_the_stage_alone(tmp_path: Path) -> None:
    layout = load_layout("windows-x64")
    staged, host, lane = tmp_path / "stage", tmp_path / "host.exe", tmp_path / "lane"
    staged.mkdir()
    _stage(staged, layout)
    before = _snapshot(staged)
    host.write_bytes(b"remote-debugging host")
    (lane / "stale").mkdir(parents=True)
    (lane / "stale" / "left.txt").write_bytes(b"from an older stage")

    image = stage_lane_package(layout, staged, host, lane)

    assert _snapshot(staged) == before
    desktop = desktop_image(layout)
    assert desktop is not None
    assert image == lane / desktop.package_path
    assert image.read_bytes() == b"remote-debugging host"
    assert not (lane / "stale").exists()
    assert (lane / "lib" / "module.py").read_bytes() == before["lib/module.py"]
    host_digest = _sha(b"remote-debugging host")
    descriptors_member = layout["files"]["service_descriptors"]
    descriptors = json.loads((lane / descriptors_member).read_bytes())
    for descriptor in descriptors:
        expected = descriptor.pop("descriptor_digest")
        assert sha256_hex(canonical_json_bytes(descriptor)) == expected
        assert descriptor["image_digest"] == host_digest
        assert [parent["image_digest"] for parent in descriptor["allowed_parent_images"]] == [host_digest]
    manifest = json.loads((lane / layout["files"]["package_manifest"]).read_text(encoding="utf-8"))
    assert manifest["files"][desktop.package_path] == host_digest
    assert manifest["files"][descriptors_member] == _sha((lane / descriptors_member).read_bytes())
    assert manifest["files"]["lib/module.py"] == _sha(before["lib/module.py"])


def test_a_changed_staged_file_is_mirrored_again(tmp_path: Path) -> None:
    layout = load_layout("windows-x64")
    staged, host, lane = tmp_path / "stage", tmp_path / "host.exe", tmp_path / "lane"
    staged.mkdir()
    _stage(staged, layout)
    host.write_bytes(b"remote-debugging host")
    stage_lane_package(layout, staged, host, lane)
    module = staged / "lib" / "module.py"
    module.write_bytes(b"print('rebuilt payload')\n")
    os.utime(module, ns=(module.stat().st_atime_ns, module.stat().st_mtime_ns + 1_000_000_000))

    stage_lane_package(layout, staged, host, lane)

    assert (lane / "lib" / "module.py").read_bytes() == b"print('rebuilt payload')\n"


def test_restage_replaces_the_host_inode_and_rebinds_descriptors(tmp_path: Path) -> None:
    layout = load_layout("windows-x64")
    staged, host, lane = tmp_path / "stage", tmp_path / "host.exe", tmp_path / "lane"
    staged.mkdir()
    _stage(staged, layout)
    old_host, new_host = b"host version one", b"host version two"
    assert len(old_host) == len(new_host)
    host.write_bytes(old_host)
    image = stage_lane_package(layout, staged, host, lane)
    old_inode = image.stat().st_ino
    host.write_bytes(new_host)

    if os.name == "posix":
        with image.open("rb") as old_image:
            stage_lane_package(layout, staged, host, lane)
            assert image.stat().st_ino != old_inode
            assert old_image.read() == old_host
    else:
        stage_lane_package(layout, staged, host, lane)

    assert image.read_bytes() == new_host
    host_digest = _sha(new_host)
    descriptor_member = layout["files"]["service_descriptors"]
    descriptors = json.loads((lane / descriptor_member).read_bytes())
    for descriptor in descriptors:
        expected = descriptor.pop("descriptor_digest")
        assert sha256_hex(canonical_json_bytes(descriptor)) == expected
        assert descriptor["image_digest"] == host_digest
        assert [parent["image_digest"] for parent in descriptor["allowed_parent_images"]] == [host_digest]
    manifest = json.loads((lane / layout["files"]["package_manifest"]).read_text(encoding="utf-8"))
    desktop = desktop_image(layout)
    assert desktop is not None
    assert manifest["files"][desktop.package_path] == host_digest
    assert manifest["files"][descriptor_member] == _sha((lane / descriptor_member).read_bytes())


def test_mirror_replaces_a_changed_image_without_rewriting_its_inode(tmp_path: Path) -> None:
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.mkdir()
    staged_image = source / "signed-image"
    staged_image.write_bytes(b"old image")
    assert mirror(source, destination, rebound=frozenset()) == 1
    image = destination / staged_image.name
    old_inode = image.stat().st_ino
    staged_image.write_bytes(b"new image")
    os.utime(staged_image, ns=(staged_image.stat().st_atime_ns, image.stat().st_mtime_ns + 1_000_000_000))

    if os.name == "posix":
        with image.open("rb") as old_image:
            assert mirror(source, destination, rebound=frozenset()) == 1
            assert image.stat().st_ino != old_inode
            assert old_image.read() == b"old image"
    else:
        assert mirror(source, destination, rebound=frozenset()) == 1
    assert image.read_bytes() == b"new image"


def test_failed_mirror_copy_keeps_the_original_and_removes_the_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "signed-image").write_bytes(b"replacement image")
    target = destination / "signed-image"
    target.write_bytes(b"original image")
    before = _snapshot(destination)

    def fail_copy(_source: Path, target_path: Path) -> None:
        target_path.write_bytes(b"partial")
        raise OSError("copy failed")

    monkeypatch.setattr(shutil, "copy2", fail_copy)
    with pytest.raises(OSError, match="copy failed"):
        mirror(source, destination, rebound=frozenset({"signed-image"}))

    assert _snapshot(destination) == before


def test_a_stage_from_another_layout_is_refused(tmp_path: Path) -> None:
    layout = load_layout("windows-x64")
    staged, host = tmp_path / "stage", tmp_path / "host.exe"
    staged.mkdir()
    _stage(staged, {**layout, "abi": "another"})
    host.write_bytes(b"remote-debugging host")
    with pytest.raises(ValueError, match="another layout"):
        stage_lane_package(layout, staged, host, tmp_path / "lane")


def test_descriptors_that_differ_from_the_manifest_are_refused(tmp_path: Path) -> None:
    layout = load_layout("windows-x64")
    staged, host = tmp_path / "stage", tmp_path / "host.exe"
    staged.mkdir()
    _stage(staged, layout)
    (staged / layout["files"]["service_descriptors"]).write_bytes(b"[]")
    host.write_bytes(b"remote-debugging host")
    with pytest.raises(ValueError, match="service descriptors differ"):
        stage_lane_package(layout, staged, host, tmp_path / "lane")
