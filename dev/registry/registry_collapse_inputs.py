"""Shared source dependency discovery and snapshot copying."""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

from dev.registry.compiler.source_evidence_fingerprint import collect_source_evidence_fingerprints


def _source_dependency_paths(source_root: Path) -> tuple[Path, ...]:
    """Enumerate every non-registry compiler input that must be isolated."""
    evidence = tuple(
        Path(path) for path, _size, _modified_ns in collect_source_evidence_fingerprints(source_root, use_cache=False)
    )
    profile_root = source_root / "registry" / "cadrumo"
    profiles = tuple(path for path in profile_root.rglob("*") if path.is_file())
    return tuple(sorted(set((*evidence, *profiles))))


def _copy_source_dependencies(paths: Iterable[Path], *, source_root: Path, destination: Path) -> None:
    """Copy exact compiler inputs while retaining source-root-relative paths."""
    resolved_root = source_root.resolve(strict=True)
    for source in paths:
        relative = source.resolve(strict=True).relative_to(resolved_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
