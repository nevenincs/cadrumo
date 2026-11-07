"""The grade-earned screen reads the derived capability probe and names the missing or hidden prerequisite.

Detector teeth on constructed revisions: a filing grade whose calculation
closure is non-empty, with no layout and no completeness manifest, is
under-supported on both prerequisites; an
applicability grade carrying a layout is under-declared on that prerequisite;
an applicability grade carrying nothing is clean. The screen never reads
fragment directories itself, so it cannot disagree with the support matrix.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportLayoutDefinition,
)
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..analysis.grade_earned import grade_findings
from .single_casilla_export_layout_support import (
    CASILLA_01,
    LEGAL_REF,
    SOURCE_REF,
    single_casilla_export_layout,
)

# A casilla the engine computes puts the revision's calculation closure above
# empty, which is when the screen demands a completeness manifest.
_COMPUTED_CASILLA = CasillaDefinition(
    id=CASILLA_01,
    number="01",
    localization_keys=("test.schema.casilla.label",),
    section=("liquidacion",),
    input_kind=InputKind.COMPUTED,
    formula="test-formula",
    legal_refs=(LEGAL_REF,),
    source_refs=(SOURCE_REF,),
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _revision(
    *,
    grade: str,
    layouts: tuple[ExportLayoutDefinition, ...],
    casillas: tuple[CasillaDefinition, ...] = (),
) -> ModeloRevision:
    year = filing_year_envelope().horizon
    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(year, 1, 1),
        period_selector=PeriodSelector(years=(year,), periods=("1T",)),
        legal_refs=(LEGAL_REF,),
        source_refs=(SOURCE_REF,),
        authority_grade=grade,
        casillas=casillas,
        export_layouts=layouts,
    )


def test_filing_grade_without_prerequisites_is_under_supported_on_each() -> None:
    findings = grade_findings(_revision(grade="filing", layouts=(), casillas=(_COMPUTED_CASILLA,)), modelo_id="000")

    assert {(f.kind, f.prerequisite) for f in findings} == {
        ("under_supported", "export_layout"),
        ("under_supported", "completeness_manifest"),
    }
    assert all(f.declared_grade == "filing" and f.revision == "test-revision" for f in findings)


def test_filing_grade_with_layout_is_under_supported_only_on_the_manifest() -> None:
    findings = grade_findings(
        _revision(grade="filing", layouts=(single_casilla_export_layout(),), casillas=(_COMPUTED_CASILLA,)),
        modelo_id="000",
    )

    assert [(f.kind, f.prerequisite) for f in findings] == [("under_supported", "completeness_manifest")]


def test_applicability_grade_carrying_a_layout_is_under_declared() -> None:
    findings = grade_findings(
        _revision(grade="applicability", layouts=(single_casilla_export_layout(),)), modelo_id="000"
    )

    assert [(f.kind, f.prerequisite) for f in findings] == [("under_declared", "export_layout")]


def test_applicability_grade_carrying_nothing_is_clean() -> None:
    assert grade_findings(_revision(grade="applicability", layouts=()), modelo_id="000") == ()
