"""Published bytecode removes runtime compilation without trusting stale source."""

from __future__ import annotations

import hashlib
import importlib.machinery
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

from ...command_execution import run_command
from .. import stdlib
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
    with pytest.raises(ValueError, match="compatible development Python"):
        compile_packages_bytecode(tmp_path / "first", prefix="cadrumo/site-packages", version="0.0.0")


def test_incremental_bytecode_compiles_only_changed_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    previous.mkdir()
    current.mkdir()
    for root in (previous, current):
        (root / "unchanged.py").write_text("answer = 41\n", encoding="utf-8")
        (root / "changed.py").write_text("answer = 41\n", encoding="utf-8")
    _compile(previous)
    inventory = {
        f"cadrumo/site-packages/{file.relative_to(previous).as_posix()}": hashlib.sha256(file.read_bytes()).hexdigest()
        for file in previous.rglob("*.pyc")
    }
    (current / "changed.py").write_text("answer = 42\n", encoding="utf-8")
    compiled: list[str] = []
    compiler = stdlib.bytecode

    def track(content: bytes, name: str, *, prefix: str) -> bytes:
        compiled.append(name)
        return compiler(content, name, prefix=prefix)

    monkeypatch.setattr(stdlib, "bytecode", track)
    compile_packages_bytecode(
        current,
        prefix="cadrumo/site-packages",
        version=".".join(map(str, sys.version_info[:3])),
        previous=previous,
        previous_files=inventory,
    )
    assert compiled == ["changed.py"]
    member = f"__pycache__/unchanged.{sys.implementation.cache_tag}.pyc"
    assert os.path.samefile(previous / member, current / member)


def test_incremental_bytecode_refuses_modified_payload_with_unchanged_hash_header(tmp_path: Path) -> None:
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    previous.mkdir()
    current.mkdir()
    for root in (previous, current):
        (root / "example.py").write_text("answer = 41\n", encoding="utf-8")
    cache = _compile(previous)
    original = cache.read_bytes()
    relative = cache.relative_to(previous)
    inventory = {f"cadrumo/site-packages/{relative.as_posix()}": hashlib.sha256(original).hexdigest()}
    cache.write_bytes(original[:16] + b"damaged marshal payload")
    compile_packages_bytecode(
        current,
        prefix="cadrumo/site-packages",
        version=".".join(map(str, sys.version_info[:3])),
        previous=previous,
        previous_files=inventory,
    )
    assert (current / relative).read_bytes() == original
    assert not os.path.samefile(cache, current / relative)


def test_stdlib_reuse_identity_detects_changes_even_with_preserved_file_metadata(tmp_path: Path) -> None:
    module = tmp_path / "example.py"
    module.write_bytes(b"answer = 41\n")
    original = stdlib.bundle_identity(tmp_path, [], {"bootstrap": b"import sys"}, "3.13.11")
    metadata = module.stat()
    module.write_bytes(b"answer = 42\n")
    os.utime(module, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    assert stdlib.bundle_identity(tmp_path, [], {"bootstrap": b"import sys"}, "3.13.11") != original
    module.write_bytes(b"answer = 41\n")
    assert stdlib.bundle_identity(tmp_path, [], {"bootstrap": b"import os"}, "3.13.11") != original


def test_optimized_builder_preserves_the_runtime_debug_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "example.py"
    source.write_text("runtime_checks = __debug__\n", encoding="utf-8")
    producer = (
        "import runpy,sys; from pathlib import Path; "
        "tools=runpy.run_path(sys.argv[1]); "
        "tools['compile_packages_bytecode'](Path(sys.argv[2]), prefix='packages', "
        "version='.'.join(map(str,sys.version_info[:3])))"
    )
    result = run_command(
        [sys.executable, "-O", "-c", producer, str(Path(stdlib.__file__)), str(tmp_path)], cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr
    monkeypatch.setattr(sys, "pycache_prefix", None)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    module = ModuleType("example")
    importlib.machinery.SourceFileLoader("example", str(source)).exec_module(module)
    assert module.runtime_checks is True


@pytest.mark.parametrize(
    ("runtime", "admitted"),
    [
        (f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}", True),
        (f"{sys.version_info[0]}.{sys.version_info[1]}.0", True),
        (f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2] + 1}", False),
        (f"{sys.version_info[0]}.{sys.version_info[1] + 1}.0", False),
        (f"{sys.version_info[0]}.{sys.version_info[1] - 1}.{sys.version_info[2]}", False),
    ],
)
def test_one_compiler_policy_admits_the_runtime_minor_at_an_equal_or_newer_patch(runtime: str, admitted: bool) -> None:
    if admitted:
        stdlib.require_bytecode_compiler(runtime)
    else:
        with pytest.raises(ValueError, match="compatible development Python"):
            stdlib.require_bytecode_compiler(runtime)
