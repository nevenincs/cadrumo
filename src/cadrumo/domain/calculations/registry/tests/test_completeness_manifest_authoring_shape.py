"""Calculation-completeness manifests have one canonical authoring shape."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path

import pytest

from .....core.resources._boundary import bundled_path
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _completeness_manifest_fragments(modelos_root: Path) -> tuple[tuple[Path, str, str], ...]:
    fragments: list[tuple[Path, str, str]] = []
    for path in modelos_root.glob("*/revisions/**/*.toml"):
        if b"completeness_manifest" not in path.read_bytes():
            continue
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        revisions = data.get("revisions")
        if not isinstance(revisions, Mapping):
            continue
        for revision_id, revision in revisions.items():
            if isinstance(revision, Mapping) and "completeness_manifest" in revision:
                fragments.append((path, path.relative_to(modelos_root).parts[0], revision_id))
    return tuple(fragments)


def test_completeness_manifests_use_the_canonical_fragment_anchor() -> None:
    """Every loaded manifest is authored below one stable section path."""
    modelos, _catalogues = _committed_registry_tree()
    expected = {
        (modelo.id, revision_id)
        for modelo in modelos
        for revision_id, revision in modelo.revisions.items()
        if revision.completeness_manifest is not None
    }
    modelos_root = bundled_path("registry", "aeat", "modelos")
    anchors = {
        (path.parents[3].name, path.parents[1].name)
        for path in modelos_root.glob(
            # The committed anchor is hyphenated -- all 69 of them. This glob named it
            # with an underscore, matched nothing, and left `anchors` empty, so the
            # equality below failed for every modelo at once and the gate could never
            # pass. A gate that cannot pass asserts nothing.
            "*/revisions/*/completeness_manifest/0001-completeness-manifest.toml",
        )
    }

    assert anchors == expected
    misplaced = tuple(
        path
        for path, modelo_id, revision_id in _completeness_manifest_fragments(modelos_root)
        if path.parent != modelos_root / modelo_id / "revisions" / revision_id / "completeness_manifest"
    )
    assert misplaced == ()
