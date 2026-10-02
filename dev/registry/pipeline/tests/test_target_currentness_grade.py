"""Currentness proves a committed generated tree at the grade its edition declares.

A calculation-grade edition never selects at filing grade, so proving its tree
at the filing default refused a tree that reproduces byte for byte and reported
it drifted. The edition is found in the live authority rather than named, so the
proof follows whichever edition carries a committed tree below filing grade.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryError

from ...compiler.authority import compiled_bundled_authority
from ..cli import (
    GeneratedTreeInvocation,
    TargetCurrentnessState,
    at_edition_grade,
    check_prepared_invocation,
    prepare_generated_tree_invocation,
    target_currentness,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _below_filing_target() -> tuple[str, str, RegistryAuthorityGrade]:
    """The first edition below filing grade that carries a committed generated export tree."""
    authority = compiled_bundled_authority()
    modelos_root = bundled_path("registry", "aeat", "modelos")
    for modelo_dir in sorted(path for path in modelos_root.iterdir() if path.is_dir()):
        for revision_id, revision in sorted(authority.modelo(modelo_dir.name).revisions.items()):
            grade = revision.effective_authority_grade
            if grade is RegistryAuthorityGrade.FILING:
                continue
            if (modelo_dir / "revisions" / str(revision_id) / "export" / "_generation.provenance.json").is_file():
                return modelo_dir.name, str(revision_id), grade
    pytest.fail("no edition below filing grade carries a committed generated tree to prove currentness against")


def test_a_tree_below_filing_grade_is_current_at_its_own_grade() -> None:
    modelo, revision, _grade = _below_filing_target()

    fact = target_currentness(modelo, revision, None, None)

    assert fact.state is TargetCurrentnessState.CURRENT, fact.detail


def test_the_same_tree_proven_at_filing_grade_is_refused() -> None:
    """Detector teeth: the filing default the currentness proof used to demand refuses this tree."""
    modelo, revision, grade = _below_filing_target()
    authority = compiled_bundled_authority()
    selected = authority.modelo(modelo).revisions[revision]
    design_refs = [
        str(ref)
        for ref in selected.source_refs
        if (source := authority.catalogues.sources.get(ref)) is not None
        and source.kind == "record_design"
        and source.record_design_epoch is not None
    ]
    (source_ref,) = design_refs
    year = selected.valid_from.year
    invocation = GeneratedTreeInvocation(
        modelo, revision, source_ref, year, str(selected.period_selector.periods_for_year(year)[0])
    )
    with tempfile.TemporaryDirectory(prefix="cadrumo-currentness-grade-") as temporary:
        prepared = prepare_generated_tree_invocation(invocation, Path(temporary), authority=authority)
        assert prepared.validation.required_grade is RegistryAuthorityGrade.FILING
        assert at_edition_grade(prepared, grade).validation.required_grade is grade
        with pytest.raises((RegistryError, ValueError)):
            check_prepared_invocation(prepared)
