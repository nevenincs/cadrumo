"""Enumerate package root candidates for import authority validation."""

from __future__ import annotations

from pathlib import Path


def _collect_root_candidate(
    entry: Path, base: Path, repository: Path, candidates: set[str], source_modules: set[str]
) -> None:
    """Collect root candidate."""
    if entry.name.startswith("."):
        return
    if base == repository / "src" and entry.is_file() and entry.suffix == ".py":
        source_modules.add(entry.stem)
        return
    if not entry.is_dir():
        return
    if (entry / "__init__.py").is_file() or (base == repository / "src" and any(entry.rglob("*.py"))):
        candidates.add(entry.name)


def inspect_root_base(
    base: Path, repository: Path, candidates: set[str], source_modules: set[str], findings: list[str]
) -> None:
    """Inspect one source root and record its package candidates."""
    if not base.is_dir():
        return
    try:
        entries = tuple(base.iterdir())
    except OSError as exc:
        findings.append(f"[AUTHORITY_CONFIG] cannot inspect source-root directory {base}: {exc}")
        return
    for entry in entries:
        _collect_root_candidate(entry, base, repository, candidates, source_modules)
