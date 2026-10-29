"""The one canonical repo-root and text-encoding constants for `dev/` tooling.

`dev/` scripts run both as `python -m dev.<pkg>.<module>` and, for a small
number of entrypoints that predate the interpreter having `dev` on
`sys.path`, as bare scripts (`python dev/<pkg>/<module>.py`). A bare-script
invocation needs its own local `Path(__file__).resolve().parents[N]` to seed
`sys.path` before `dev` is importable at all — that bootstrap line is not
duplication, it is the precondition for reaching this module, and it stays
local. Every other `dev/` module reaches `dev` normally and repoints here.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
TEMP_ROOT: Final[Path] = REPO_ROOT / ".tmp"
"""The checkout's sole root for disposable developer and agent working output."""
UTF_8: Final[str] = "utf-8"


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
    value = os.environ.get("CADRUMO_TEMP_DIR", "") if override is None else str(override)
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


COMPONENT_PINS_ROOT: Final[Path] = REPO_ROOT / "native" / "component-pins"
"""The folder holding the pin tables the native component engine reads; assembly stages it whole."""

# Standalone dev commands may not run from an editable installation. Make the
# checkout's source package importable before dev tooling reaches its storage
# path authority.
_SOURCE_ROOT = REPO_ROOT / "src"
if _SOURCE_ROOT.is_dir() and str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

# Importing path constants must not configure tools, create directories or
# override machine-managed caches. Test runners own their explicit isolation.

AUTHORITY_ROOT_ENV: Final[str] = "CADRUMO_AUTHORITY_ROOT"
"""Environment variable naming the directory holding the published authority."""

DEFAULT_AUTHORITY_ROOT: Final[Path] = REPO_ROOT / ".authority"
"""Where a checkout keeps its published authority, outside the packaged tree.

The repo-root ``conftest.py`` spells the same path out in pure stdlib, because
this module is private to ``dev`` and nothing the test suite already imports
reaches it. The two definitions cross-reference each other so a future edit to
one is not made deaf to the other."""

# The published authority is generated output that no longer lives inside the
# packaged tree, so every `python -m dev.*` entry point and every recipe that
# reaches one would otherwise need the variable exported by hand. Seeding it
# here, at the shared path-constants entry point, makes a checkout resolve its
# own authority with no operator setup. An explicit value always wins: a blank
# one is treated as unset, matching Settings' `env_ignore_empty` behaviour, so a
# variable exported empty by a shell profile does not resolve the authority to
# the process's current working directory.
if not os.environ.get(AUTHORITY_ROOT_ENV, "").strip():
    os.environ[AUTHORITY_ROOT_ENV] = str(DEFAULT_AUTHORITY_ROOT)

# Windows starts a Python process with its streams bound to the ANSI codepage
# (cp1252 on a stock installation). Configure the developer process at the
# shared path-constants entry point, after the package initializer has loaded,
# so tool output can carry the repository's Unicode identifiers safely.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding=UTF_8)

__all__ = [
    "AUTHORITY_ROOT_ENV",
    "DEFAULT_AUTHORITY_ROOT",
    "REPO_ROOT",
    "TEMP_ROOT",
    "UTF_8",
    "prepare_temp_root",
    "resolve_temporary_output",
]
