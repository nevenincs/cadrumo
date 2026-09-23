"""Every TOML under the registry root is part of the identity that keys compilation and verdicts.

The walked identity keys the compiled registry, the disk pickle and the recorded
validation verdict. A TOML outside the walk is a compiler input whose edit keeps
the old identity, so a recorded clean verdict skips validating the changed file
and the compile cache serves the previous result. Fifty such files once sat
outside it -- the IVA runtime catalogues among them -- and the compiler's own
refusal gates stopped firing on an edited copy wherever a clean verdict had been
recorded for the untouched tree.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ..authority import _compile_validated_authority_uncached
from ..identity import compute_walked_tree_digest
from ..loader_fingerprints import collect_registry_tree_fingerprints
from ..validation_verdict_cache import validation_verdict_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _bundled_registry_root() -> Path:
    return Path(bundled_path("registry", "aeat")).resolve()


def test_every_registry_toml_is_a_fingerprinted_input() -> None:
    """Enumerated independently of the walk, so a directory the walk forgets is named here."""
    registry = _bundled_registry_root()
    walked = {
        Path(row[0]).resolve()
        for row in collect_registry_tree_fingerprints(registry, use_cache=False)
        if str(row[0]).endswith(".toml")
    }

    unfingerprinted = sorted(
        path.relative_to(registry).as_posix() for path in registry.rglob("*.toml") if path.resolve() not in walked
    )

    assert unfingerprinted == [], (
        f"{len(unfingerprinted)} registry TOML(s) outside the identity: {unfingerprinted[:10]}"
    )


def test_an_edit_to_any_non_modelo_directory_changes_the_identity_and_the_verdict_key(tmp_path: Path) -> None:
    """One edited file per top-level catalogue directory must re-key both caches."""
    registry = tmp_path / "registry" / "aeat"
    shutil.copytree(_bundled_registry_root(), registry)
    probes = [
        next(iter(sorted(directory.rglob("*.toml"))))
        for directory in sorted(registry.iterdir())
        if directory.is_dir() and directory.name != "modelos" and any(directory.rglob("*.toml"))
    ]
    assert len(probes) >= 5, "the copy holds too few catalogue directories to prove anything"

    def keys() -> tuple[str, str]:
        rows = collect_registry_tree_fingerprints(registry.resolve(), use_cache=False)
        scope = validation_verdict_scope(
            registry_root=registry.resolve(),
            fingerprints=rows,
            source_receipt="fixed-source-receipt",
            compiler_identity_digest="fixed-compiler-identity",
        )
        return compute_walked_tree_digest(rows), scope.registry_key

    unchanged: list[str] = []
    for probe in probes:
        before = keys()
        probe.write_text(probe.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        after = keys()
        if after[0] == before[0] or after[1] == before[1]:
            unchanged.append(probe.relative_to(registry).as_posix())

    assert unchanged == [], f"an edit left the identity or verdict key unchanged: {unchanged}"


def test_every_file_the_compiler_opens_under_the_registry_root_is_fingerprinted(tmp_path: Path) -> None:
    """Observed rather than enumerated: whatever the compile actually reads must key its caches.

    The enumeration above covers the TOML the tree holds today. This covers
    what the compiler really opens, so an input in a new format -- a JSON
    artefact, a text sidecar -- that the walk does not know about is named too.
    """
    registry = (tmp_path / "registry" / "aeat").resolve()
    shutil.copytree(_bundled_registry_root(), registry)
    opened: set[Path] = set()
    recording = [True]

    def record_open(event: str, arguments: tuple[object, ...]) -> None:
        if not recording[0] or event != "open" or not arguments:
            return
        candidate = arguments[0]
        if isinstance(candidate, (str, os.PathLike)):
            path = Path(os.fspath(candidate))
            if path.is_absolute() and path.is_relative_to(registry) and path.is_file():
                opened.add(path.resolve())

    sys.addaudithook(record_open)
    try:
        _compile_validated_authority_uncached(registry, Path(bundled_path()), verdicts=None)
    finally:
        recording[0] = False
    fingerprinted = {Path(row[0]).resolve() for row in collect_registry_tree_fingerprints(registry, use_cache=False)}

    assert opened, "the compile opened nothing under the copied root, so the comparison would be vacuous"
    unkeyed = sorted(path.relative_to(registry).as_posix() for path in opened - fingerprinted)
    assert unkeyed == [], f"the compiler read {len(unkeyed)} file(s) its identity does not key: {unkeyed[:10]}"
