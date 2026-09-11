"""Behavioral ownership proofs for mutable development authority compilation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from dev.registry.compiler.authority_state import (
    authoring_root_pair,
    cached_compilation,
    compiler_reset,
    source_evidence_receipt,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _compile_with_receipt(
    registry_root: Path,
    source_root: Path,
    source_file: Path,
    builds: list[object],
) -> object:
    """Exercise the real development cache at its mutable-tree handoff."""
    return cached_compilation(
        authoring_root_pair(registry_root, source_root),
        registry_identity_digest="registry-receipt",
        source_receipt=source_evidence_receipt(
            ((str(source_file), source_file.stat().st_size, source_file.stat().st_mtime_ns),)
        ),
        build=lambda: builds.append(object()) or cast(ValidatedRegistryAuthority, builds[-1]),
    )


def test_development_cache_reuses_an_unchanged_authoring_receipt(tmp_path: Path) -> None:
    """An unchanged mutable input compiles once and returns its owned result."""
    registry_root = tmp_path / "registry"
    source_root = tmp_path / "sources"
    registry_root.mkdir()
    source_root.mkdir()
    source_file = source_root / "official.xml"
    source_file.write_bytes(b"published-source")
    builds: list[object] = []

    first = _compile_with_receipt(registry_root, source_root, source_file, builds)
    later = _compile_with_receipt(registry_root, source_root, source_file, builds)

    assert first is later
    assert len(builds) == 1


def test_development_cache_recompiles_for_equal_metadata_source_rewrite(tmp_path: Path) -> None:
    """A same-size restored-mtime source rewrite cannot reuse a stale compiler result."""
    registry_root = tmp_path / "registry"
    source_root = tmp_path / "sources"
    registry_root.mkdir()
    source_root.mkdir()
    source_file = source_root / "official.xml"
    source_file.write_bytes(b"source-A")
    original_mtime = source_file.stat().st_mtime_ns
    builds: list[object] = []

    first = _compile_with_receipt(registry_root, source_root, source_file, builds)
    source_file.write_bytes(b"source-B")
    os.utime(source_file, ns=(original_mtime, original_mtime))
    later = _compile_with_receipt(registry_root, source_root, source_file, builds)

    assert first is not later
    assert len(builds) == 2


def test_development_reset_discards_a_compiler_result(tmp_path: Path) -> None:
    """A maintenance reset makes the next mutable-tree read compile afresh."""
    registry_root = tmp_path / "registry"
    source_root = tmp_path / "sources"
    registry_root.mkdir()
    source_root.mkdir()
    source_file = source_root / "official.xml"
    source_file.write_bytes(b"published-source")
    builds: list[object] = []

    first = _compile_with_receipt(registry_root, source_root, source_file, builds)
    with compiler_reset():
        pass
    later = _compile_with_receipt(registry_root, source_root, source_file, builds)

    assert first is not later
    assert len(builds) == 2
