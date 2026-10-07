"""Published bytecode removes runtime compilation without trusting stale source."""

from __future__ import annotations

import importlib.machinery
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

from ..stdlib import compile_packages_bytecode

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _compile(root: Path) -> Path:
    compile_packages_bytecode(root, prefix="cadrumo/site-packages", version=".".join(map(str, sys.version_info[:3])))
    return root / "__pycache__" / f"example.{sys.implementation.cache_tag}.pyc"


def test_published_cache_loads_without_compiling_and_keeps_runtime_files_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "example.py"
    source.write_text("answer = 41\n", encoding="utf-8")
    builder_cache = tmp_path / "builder-cache"
    monkeypatch.setattr(sys, "pycache_prefix", str(builder_cache))
    cache = _compile(tmp_path)
    assert cache.parent == tmp_path / "__pycache__"
    assert not builder_cache.exists()
    original = cache.read_bytes()
    monkeypatch.setattr(sys, "pycache_prefix", None)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    def refuse_compilation(*args: object, **kwargs: object) -> None:
        pytest.fail("A matching published cache must not compile the source again")

    monkeypatch.setattr(importlib.machinery.SourceFileLoader, "source_to_code", refuse_compilation)
    module = ModuleType("example")
    importlib.machinery.SourceFileLoader("example", str(source)).exec_module(module)
    assert module.answer == 41
    assert cache.read_bytes() == original


def test_source_change_with_identical_size_and_timestamp_does_not_reuse_stale_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "example.py"
    source.write_text("answer = 41\n", encoding="utf-8")
    cache = _compile(tmp_path)
    monkeypatch.setattr(sys, "pycache_prefix", None)
    original = cache.read_bytes()
    metadata = source.stat()
    source.write_text("answer = 42\n", encoding="utf-8")
    os.utime(source, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    module = ModuleType("example")
    importlib.machinery.SourceFileLoader("example", str(source)).exec_module(module)
    assert module.answer == 42
    assert cache.read_bytes() == original


def test_bytecode_is_identical_across_package_roots_and_compiler_pin_is_enforced(tmp_path: Path) -> None:
    outputs = []
    for name in ("first", "another"):
        root = tmp_path / name
        root.mkdir()
        (root / "example.py").write_text("answer = 41\n", encoding="utf-8")
        outputs.append(_compile(root).read_bytes())
    assert outputs[0] == outputs[1]
    with pytest.raises(ValueError, match="exact pinned development Python"):
        compile_packages_bytecode(tmp_path / "first", prefix="cadrumo/site-packages", version="0.0.0")
