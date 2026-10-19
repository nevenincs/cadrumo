"""Assembly with the shared digest cache reuses only what is unchanged, and stages what a full build would."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

import pytest

from ..assembly_transaction import assembly_candidate
from ..cached_command import inventory
from ..hashing import digest, digest_cache

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LONG_AGO = time.time_ns() - 3600 * 1_000_000_000


def _write(path: Path, content: bytes, *, at: int = _LONG_AGO) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.utime(path, ns=(at, at))
    return path


def _assemble(dependencies: Path, destination: Path, build: Path) -> None:
    """Stage ``dependencies`` the way assembly copies them, and record the package receipt."""
    with digest_cache(build), assembly_candidate(destination, "package.json") as (candidate, reuse):
        shutil.copytree(dependencies, candidate / "packages", copy_function=reuse.copy)
        files = {
            path.relative_to(candidate).as_posix(): digest(path)
            for path in sorted(candidate.rglob("*"))
            if path.is_file()
        }
        (candidate / "package.json").write_text(json.dumps({"files": files}), encoding="utf-8")


def test_a_changed_dependency_is_copied_again_and_an_unchanged_one_reused(tmp_path: Path) -> None:
    dependencies, destination, build = tmp_path / "site-packages", tmp_path / "app", tmp_path / "build"
    _write(dependencies / "kept.py", b"kept = 1\n")
    _write(dependencies / "changed.py", b"value = 1\n")
    _assemble(dependencies, destination, build)
    kept = destination / "packages" / "kept.py"
    before = kept.stat()
    # The same size, written later: only a fresh digest tells the bytes apart.
    _write(dependencies / "changed.py", b"value = 2\n", at=_LONG_AGO + 1_000_000_000)
    _assemble(dependencies, destination, build)
    assert (destination / "packages" / "changed.py").read_bytes() == b"value = 2\n"
    assert (destination / "packages" / "kept.py").stat().st_ino == before.st_ino


def test_a_deleted_dependency_leaves_the_stage(tmp_path: Path) -> None:
    dependencies, destination, build = tmp_path / "site-packages", tmp_path / "app", tmp_path / "build"
    _write(dependencies / "kept.py", b"kept = 1\n")
    _write(dependencies / "removed.py", b"removed = 1\n")
    _assemble(dependencies, destination, build)
    (dependencies / "removed.py").unlink()
    _assemble(dependencies, destination, build)
    assert not (destination / "packages" / "removed.py").exists()
    assert (destination / "packages" / "kept.py").is_file()


def test_the_cached_inventory_equals_a_full_one(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    for index in range(30):
        _write(tree / f"module{index}.py", f"value = {index}\n".encode())
    single = _write(tmp_path / "pyproject.toml", b"[project]\n")
    paths = [str(tree), str(single)]
    full = inventory(paths)
    with digest_cache(tmp_path / "build"):
        cold = inventory(paths)
    with digest_cache(tmp_path / "build"):
        warm = inventory(paths)
    _write(tree / "module3.py", b"value = 'three'\n", at=_LONG_AGO + 1_000_000_000)
    changed = inventory(paths)
    with digest_cache(tmp_path / "build"):
        rehashed = inventory(paths)
    assert full == cold == warm
    assert rehashed == changed != full
