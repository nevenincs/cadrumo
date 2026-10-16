"""Candidate assembly preserves the installed stage and reuses only safe bytes."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ..assembly_transaction import AssemblyReuse, assembly_candidate
from ..hashing import digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _package(root: Path, members: dict[str, bytes]) -> None:
    for member, content in members.items():
        path = root / member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (root / "package.json").write_text(
        json.dumps({"files": {member: digest(root / member) for member in members}}), encoding="utf-8"
    )


def test_failed_candidate_retains_previous_package_and_cleans_only_candidate(tmp_path: Path) -> None:
    destination = tmp_path / "app"
    _package(destination, {"data": b"prior package"})
    original = (destination / "data").stat()
    with (
        pytest.raises(ValueError, match="assembly failed"),
        assembly_candidate(destination, "package.json") as (candidate, _),
    ):
        (candidate / "data").write_bytes(b"incomplete new package")
        raise ValueError("assembly failed")
    assert (destination / "data").read_bytes() == b"prior package"
    assert (destination / "data").stat().st_ino == original.st_ino
    assert sorted(path.name for path in tmp_path.iterdir()) == ["app"]


def test_publication_failure_restores_previous_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = tmp_path / "app"
    _package(destination, {"data": b"prior package"})
    rename = Path.rename

    def fail_candidate(path: Path, target: Path) -> Path:
        if "-assembly-" in path.name and not path.name.endswith("-previous"):
            raise OSError("publication failed")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_candidate)
    with (
        pytest.raises(OSError, match="publication failed"),
        assembly_candidate(destination, "package.json") as (candidate, _),
    ):
        (candidate / "data").write_bytes(b"new package")
    assert (destination / "data").read_bytes() == b"prior package"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["app"]


@pytest.mark.parametrize("member", ["data.bin", "library/module.py"])
def test_equal_immutable_members_reuse_prior_files_without_aliasing_inputs(tmp_path: Path, member: str) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"stable content")
    destination = tmp_path / "app"
    _package(destination, {member: source.read_bytes()})
    with assembly_candidate(destination, "package.json") as (candidate, reuse):
        target = candidate / member
        target.parent.mkdir(parents=True, exist_ok=True)
        reuse.copy(source, target)
        assert os.path.samefile(target, destination / member)
        assert not os.path.samefile(target, source)
    assert (destination / member).read_bytes() == b"stable content"


@pytest.mark.parametrize(
    "member,content",
    [
        ("pypdfium2_raw/bindings.py", b"source"),
        ("win32com/__init__.py", b"source"),
        ("extension.pyd", b"MZ native image"),
    ],
)
def test_mutable_adapter_inputs_are_private(tmp_path: Path, member: str, content: bytes) -> None:
    source = tmp_path / "source"
    source.write_bytes(content)
    destination = tmp_path / "app"
    _package(destination, {member: content})
    with assembly_candidate(destination, "package.json") as (candidate, reuse):
        target = candidate / member
        target.parent.mkdir(parents=True, exist_ok=True)
        reuse.copy(source, target)
        assert not os.path.samefile(target, destination / member)
        target.write_bytes(b"adapted")
        assert (destination / member).read_bytes() == content
        assert source.read_bytes() == content


def test_tampered_previous_file_is_not_reused(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"good")
    previous = tmp_path / "previous"
    _package(previous, {"data": b"good"})
    (previous / "data").write_bytes(b"evil")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    AssemblyReuse(previous, candidate, "package.json").copy(source, candidate / "data")
    assert (candidate / "data").read_bytes() == b"good"
    assert not os.path.samefile(candidate / "data", previous / "data")


def test_later_candidate_replacement_detaches_an_earlier_reused_file(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"prior bytes")
    destination = tmp_path / "app"
    _package(destination, {"data": source.read_bytes()})
    with assembly_candidate(destination, "package.json") as (candidate, reuse):
        target = candidate / "data"
        reuse.copy(source, target)
        assert os.path.samefile(target, destination / "data")
        source.write_bytes(b"replacement bytes")
        reuse.copy(source, target)
        assert target.read_bytes() == b"replacement bytes"
        assert (destination / "data").read_bytes() == b"prior bytes"


def test_windows_reuses_moved_native_bytes_without_exposing_the_producer_input(tmp_path: Path) -> None:
    source = tmp_path / "source.pyd"
    source.write_bytes(b"MZ extension")
    previous = tmp_path / "previous"
    _package(previous, {"native/packages/module.pyd": source.read_bytes()})
    manifest = previous / "package.json"
    document = json.loads(manifest.read_bytes())
    document["relocation"] = {"packages/module.pyd": "native/packages/module.pyd"}
    manifest.write_text(json.dumps(document), encoding="utf-8")
    candidate = tmp_path / "candidate"
    target = candidate / "packages/module.pyd"
    target.parent.mkdir(parents=True)
    AssemblyReuse(previous, candidate, "package.json", rewrite_native=False).copy(source, target)
    assert os.path.samefile(target, previous / "native/packages/module.pyd")
    assert not os.path.samefile(target, source)


@pytest.mark.parametrize("rewrite_native", [False, True])
def test_relocated_authority_reuses_verified_final_members(tmp_path: Path, rewrite_native: bool) -> None:
    source = tmp_path / "registry.json"
    source.write_bytes(b'{"published": true}')
    previous = tmp_path / "previous"
    _package(previous, {"data/authority/models/registry.json": source.read_bytes()})
    manifest = previous / "package.json"
    document = json.loads(manifest.read_bytes())
    document["layout"] = {"paths": {"packages": "cadrumo/site-packages", "authority": "data/authority"}}
    manifest.write_text(json.dumps(document), encoding="utf-8")
    candidate = tmp_path / "candidate"
    target = candidate / "cadrumo/site-packages/cadrumo/_data/registry/authority/models/registry.json"
    target.parent.mkdir(parents=True)
    AssemblyReuse(previous, candidate, "package.json", rewrite_native=rewrite_native).copy(source, target)
    assert os.path.samefile(target, previous / "data/authority/models/registry.json")
    assert not os.path.samefile(target, source)


def test_corrupt_relocation_receipt_cannot_link_files_outside_the_previous_package(tmp_path: Path) -> None:
    source = tmp_path / "outside.pyd"
    source.write_bytes(b"MZ extension")
    previous = tmp_path / "previous"
    _package(previous, {"unused": b"unused"})
    (previous / "package.json").write_text(
        json.dumps(
            {
                "relocation": {"module.pyd": "../outside.pyd"},
                "files": {"../outside.pyd": digest(source)},
            }
        ),
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    target = candidate / "module.pyd"
    AssemblyReuse(previous, candidate, "package.json", rewrite_native=False).copy(source, target)
    assert target.read_bytes() == source.read_bytes()
    assert not os.path.samefile(target, source)
