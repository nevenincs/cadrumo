"""Calculation-completeness manifests have one canonical authoring shape."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import load_toml

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _completeness_manifest_fragments(modelos_root: Path) -> tuple[tuple[Path, str, str], ...]:
    fragments: list[tuple[Path, str, str]] = []
    swept = tuple(modelos_root.glob("*/revisions/**/*.toml"))
    assert swept, (
        f"the sweep of {modelos_root} matched no declaration; a walk that reads nothing yields "
        "no misplaced completeness manifest because it yields no manifest at all"
    )
    for path in swept:
        if b"completeness_manifest" not in path.read_bytes():
            continue
        with path.open("rb") as handle:
            data = load_toml(handle)
        revisions = data.get("revisions")
        if not isinstance(revisions, Mapping):
            continue
        for revision_id, revision in revisions.items():
            if isinstance(revision, Mapping) and "completeness_manifest" in revision:
                fragments.append((path, path.relative_to(modelos_root).parts[0], revision_id))
    return tuple(fragments)


def test_completeness_manifests_use_the_canonical_fragment_anchor() -> None:
    """Every AUTHORED manifest sits below one stable section path.

    Authored, not loaded. ``completeness_manifest`` is an inherited keyed
    family, so a revision can carry a manifest its predecessor states and
    author no fragment of its own - modelo 390's 2023 and 2024 editions do.
    Comparing the anchor against every revision that CARRIES a manifest
    therefore demands a file from editions that correctly have none, which is
    a claim about inheritance rather than about where a fragment is authored.
    """
    modelos_root = bundled_path("registry", "aeat", "modelos")
    expected = {(modelo, revision_id) for _path, modelo, revision_id in _completeness_manifest_fragments(modelos_root)}
    anchors = {
        (path.parents[3].name, path.parents[1].name)
        for path in modelos_root.glob(
            # The anchor is the DIRECTORY, and the fragment inside it is named by
            # the tree's own file convention, which is `0001-declarations.toml`
            # across every family. Naming a fragment file here pinned a spelling
            # this gate does not own: it matched nothing after the rename, left
            # `anchors` empty, and failed for every modelo at once. A gate that
            # cannot pass asserts nothing.
            "*/revisions/*/completeness_manifest/*.toml",
        )
    }

    assert anchors == expected
    misplaced = tuple(
        path
        for path, modelo_id, revision_id in _completeness_manifest_fragments(modelos_root)
        if path.parent != modelos_root / modelo_id / "revisions" / revision_id / "completeness_manifest"
    )
    assert misplaced == ()
