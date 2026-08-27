"""The authority grade is declared once, as the typed field, and never as prose again.

A revision once declared its grade twice: a leading ``# Applicability grade: ...``
comment and the typed ``authority_grade`` field. Two declarations of one fact can
disagree, and only the typed one is machine-read, so the prose was retired.

This gate holds the property the retirement established -- the marker grammar
matches nothing -- and holds it by DERIVATION over the corpus rather than by a
count, so a manifest added later cannot quietly reintroduce the second
declaration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..retire_applicability_grade_markers import (
    MARKER_PATTERN,
    MarkerDisagreementError,
    find_marker_files,
    find_mid_block_markers,
    retire_markers,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_no_revision_manifest_declares_its_grade_in_prose() -> None:
    """The marker grammar matches nothing in the committed corpus."""
    assert find_marker_files() == ()
    assert find_mid_block_markers() == ()


def test_the_typed_grade_is_still_declared_across_the_corpus() -> None:
    """Anti-vacuity: retiring the prose must not have taken the grade with it.

    A corpus that declared no grade at all would satisfy the assertion above
    while having lost the fact the markers were duplicating.
    """
    from cadrumo.core.resources import bundled_path
    from cadrumo.domain.calculations.registry.loader import load_registry_tree

    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    graded = [revision for modelo in modelos for revision in modelo.revisions.values() if revision.authority_grade]

    assert graded, "no revision declares a typed authority grade; the fact was lost, not relocated"


def test_the_detector_finds_a_planted_marker(tmp_path: Path) -> None:
    """Anti-tautology: a reintroduced marker MUST be caught."""
    manifest = tmp_path / "303" / "revisions" / "2025"
    manifest.mkdir(parents=True)
    (manifest / "revision.toml").write_text(
        '[revisions."2025"]\n# Applicability grade: planted\nauthority_grade = "applicability"\n',
        encoding="utf-8",
    )

    found = find_marker_files(tmp_path)

    assert [marker.path.name for marker in found] == ["revision.toml"]


def test_a_marker_embedded_in_grounding_prose_is_not_retired(tmp_path: Path) -> None:
    """A mid-block grade phrase is reported for a reader, never deleted.

    Modelo 122 is the real case: its grade phrase sat inside a block carrying
    orden citations and the reasoning for having no calendar deadline windows.
    Retiring that block would have deleted grounding to remove a redundancy.
    """
    manifest = tmp_path / "122" / "revisions" / "2017"
    manifest.mkdir(parents=True)
    (manifest / "revision.toml").write_text(
        '[revisions."2017"]\nauthority_grade = "applicability"\n'
        "# Grounded in orden-hfp-105-2017 art 5.\n"
        "# Applicability grade: header casillas only. The diseño IS bundled.\n",
        encoding="utf-8",
    )

    assert find_marker_files(tmp_path) == ()
    assert [path.name for path in find_mid_block_markers(tmp_path)] == ["revision.toml"]
    assert retire_markers(tmp_path, apply=False) == ()
    assert "Grounded in orden-hfp-105-2017" in (manifest / "revision.toml").read_text(encoding="utf-8")


def test_a_marker_disagreeing_with_the_typed_grade_refuses(tmp_path: Path) -> None:
    """A cleanup may not choose which of two disagreeing declarations wins."""
    manifest = tmp_path / "303" / "revisions" / "2025"
    manifest.mkdir(parents=True)
    (manifest / "revision.toml").write_text(
        '[revisions."2025"]\n# Applicability grade: says one thing\nauthority_grade = "filing"\n',
        encoding="utf-8",
    )

    with pytest.raises(MarkerDisagreementError, match="may not choose"):
        retire_markers(tmp_path, apply=False)


def test_the_retirement_is_idempotent(tmp_path: Path) -> None:
    """Running it again on a retired corpus does nothing."""
    manifest = tmp_path / "303" / "revisions" / "2025"
    manifest.mkdir(parents=True)
    target = manifest / "revision.toml"
    target.write_text(
        '[revisions."2025"]\n# Applicability grade: planted\nauthority_grade = "applicability"\n',
        encoding="utf-8",
    )

    assert retire_markers(tmp_path, apply=True)
    after = target.read_text(encoding="utf-8")

    assert retire_markers(tmp_path, apply=True) == ()
    assert target.read_text(encoding="utf-8") == after
    assert 'authority_grade = "applicability"' in after
    assert not MARKER_PATTERN.search(after)
