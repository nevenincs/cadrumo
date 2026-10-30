"""Validate and prepare disposable output within the owning checkout or enrolled native build."""

from __future__ import annotations

import json
from pathlib import Path

from ._paths import REPO_ROOT, TEMP_ROOT


def _native_preset_sources() -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for preset_file, source in (
        (REPO_ROOT / "CMakePresets.json", REPO_ROOT),
        (REPO_ROOT / "native/cmake/distribution/CMakePresets.json", REPO_ROOT / "native/cmake/distribution"),
    ):
        for preset in json.loads(preset_file.read_text(encoding="utf-8"))["configurePresets"]:
            if preset.get("hidden", False):
                continue
            name = preset["name"]
            if name in sources:
                raise ValueError(f"Ambiguous native build preset: {name}")
            sources[name] = source
    return sources


def _native_declared_members(enrolled: Path, members: dict[str, str]) -> list[Path]:
    declared = []
    for member in members.values():
        relative_member = Path(member)
        if not relative_member.parts or relative_member.drive or relative_member.root or ".." in relative_member.parts:
            raise ValueError(f"Invalid native output declaration: {member}")
        declared.append(enrolled / relative_member)
    return declared


def _refuse_link(path: Path) -> None:
    if path.is_symlink() or path.is_junction():
        raise ValueError(f"Temporary output must not follow a link: {path}")


def _validate_native_output(candidate: Path, build_root: Path) -> None:
    relative = candidate.relative_to(build_root)
    if len(relative.parts) < 2:
        raise ValueError("Native temporary output must be below an enrolled build directory")
    enrolled = build_root / relative.parts[0]
    for directory in (build_root, enrolled):
        _refuse_link(directory)
    sources = _native_preset_sources()
    manifest = enrolled / "build-paths.json"
    if manifest.is_symlink() or manifest.is_junction() or not manifest.is_file():
        raise ValueError(f"Native temporary output has no matching build-path manifest: {candidate}")
    document = json.loads(manifest.read_text(encoding="utf-8"))
    if enrolled.name not in sources or Path(document["source"]) != sources[enrolled.name]:
        raise ValueError(f"Native temporary output has no matching build-path manifest: {candidate}")
    declared = _native_declared_members(enrolled, document.get("paths", {}))
    if not any(candidate.is_relative_to(member) for member in declared):
        raise ValueError(f"Native temporary output is not a declared build member: {candidate}")


def resolve_temporary_output(*, override: str | Path | None = None) -> Path:
    """Validate a complete temporary destination before any write or removal."""
    selected = TEMP_ROOT
    value = "" if override is None else str(override)
    candidate = Path(value.strip()) if value.strip() else TEMP_ROOT
    if ".." in candidate.parts:
        raise ValueError(f"Temporary output escapes its declared root through traversal: {candidate}")
    build_root = REPO_ROOT / "build"
    if candidate.is_absolute() and candidate.is_relative_to(build_root):
        _validate_native_output(candidate, build_root)
        selected = candidate
    elif candidate.is_absolute() and candidate.is_relative_to(TEMP_ROOT):
        selected = candidate
    current = selected
    while current != REPO_ROOT:
        _refuse_link(current)
        current = current.parent
    if selected.resolve() != REPO_ROOT.resolve() / selected.relative_to(REPO_ROOT):
        raise ValueError(f"Temporary output escapes the checkout: {selected}")
    return selected


def prepare_temp_root(*, override: str | Path | None = None) -> Path:
    """Prepare general scratch or an explicitly admitted native build temporary path."""
    selected = resolve_temporary_output(override=override)
    selected.mkdir(parents=True, exist_ok=True)
    return selected


__all__ = ["prepare_temp_root", "resolve_temporary_output"]
