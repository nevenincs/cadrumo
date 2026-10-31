"""The grade-earned screen reads the derived capability probe and names the missing or hidden prerequisite.

Detector teeth on constructed revisions: a filing grade with no layout and no
completeness manifest is under-supported on both prerequisites; an
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
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from ..analysis.grade_earned import grade_findings
from .single_casilla_export_layout_support import (
    LEGAL_REF,
    SOURCE_REF,
    single_casilla_export_layout,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _revision(*, grade: str, layouts: tuple[ExportLayoutDefinition, ...]) -> ModeloRevision:
    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=(LEGAL_REF,),
        source_refs=(SOURCE_REF,),
        authority_grade=grade,
        export_layouts=layouts,
    )


def test_filing_grade_without_prerequisites_is_under_supported_on_each() -> None:
    findings = grade_findings(_revision(grade="filing", layouts=()), modelo_id="000")

    assert {(f.kind, f.prerequisite) for f in findings} == {
        ("under_supported", "export_layout"),
        ("under_supported", "completeness_manifest"),
    }
    assert all(f.declared_grade == "filing" and f.revision == "test-revision" for f in findings)


def test_filing_grade_with_layout_is_under_supported_only_on_the_manifest() -> None:
    findings = grade_findings(_revision(grade="filing", layouts=(single_casilla_export_layout(),)), modelo_id="000")

    assert [(f.kind, f.prerequisite) for f in findings] == [("under_supported", "completeness_manifest")]


def test_applicability_grade_carrying_a_layout_is_under_declared() -> None:
    findings = grade_findings(
        _revision(grade="applicability", layouts=(single_casilla_export_layout(),)), modelo_id="000"
    )

    assert [(f.kind, f.prerequisite) for f in findings] == [("under_declared", "export_layout")]


def test_applicability_grade_carrying_nothing_is_clean() -> None:
    assert grade_findings(_revision(grade="applicability", layouts=()), modelo_id="000") == ()
