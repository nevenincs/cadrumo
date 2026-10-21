"""Publishing package bytecode in parallel leaves exactly what a serial pass leaves."""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import pytest

from .. import stdlib
from ..stdlib import compile_packages_bytecode

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_VERSION = ".".join(map(str, sys.version_info[:3]))
_PREFIX = "cadrumo/site-packages"


def _package(root: Path, changed: str = "") -> None:
    for index in range(60):
        module = root / f"package{index % 5}" / f"module{index}.py"
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(f"value = {index}\n{changed if index == 7 else ''}", encoding="utf-8")
    (root / "top.py").write_text("top = True\n", encoding="utf-8")


def _tree(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _manifest(root: Path) -> dict[str, str]:
    return {f"{_PREFIX}/{name}": hashlib.sha256(content).hexdigest() for name, content in _tree(root).items()}


def _publish(root: Path, previous: Path | None = None) -> dict[str, bytes]:
    compile_packages_bytecode(
        root,
        prefix=_PREFIX,
        version=_VERSION,
        previous=previous,
        previous_files=_manifest(previous) if previous is not None else None,
    )
    return _tree(root)


def test_the_parallel_pass_publishes_what_the_serial_pass_does(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("serial", "parallel", "previous"):
        _package(tmp_path / name)
    parallel = _publish(tmp_path / "parallel")
    monkeypatch.setattr(stdlib, "BYTECODE_WORKERS", 1)
    serial = _publish(tmp_path / "serial")
    assert parallel == serial
    assert sum(name.endswith(".pyc") for name in parallel) == 61


def test_reuse_and_recompilation_are_the_same_in_parallel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    previous = tmp_path / "previous"
    _package(previous)
    _publish(previous)
    for name in ("serial", "parallel"):
        # One source changed since the previous stage: only its cache is compiled again.
        _package(tmp_path / name, changed="extra = 1\n")
    parallel = _publish(tmp_path / "parallel", previous)
    monkeypatch.setattr(stdlib, "BYTECODE_WORKERS", 1)
    serial = _publish(tmp_path / "serial", previous)
    assert parallel == serial
    tag = sys.implementation.cache_tag
    changed = f"package2/__pycache__/module7.{tag}.pyc"
    kept = f"package0/__pycache__/module0.{tag}.pyc"
    assert parallel[changed] != _tree(previous)[changed]
    assert parallel[kept] == _tree(previous)[kept]
    shutil.rmtree(previous)
