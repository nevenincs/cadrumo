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

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from ..analysis.grade_earned import grade_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-35-2006:art-test"
_SOURCE_REF = "aeat-test-source-001"
_CASILLA_01 = validated_casilla_id("01", surface="_CASILLA_01")


def _layout() -> ExportLayoutDefinition:
    field = ExportFieldDefinition(
        id="importe",
        offset=1,
        length=10,
        kind=CasillaFieldKind.CASILLA,
        casilla_id=_CASILLA_01,
        data_type="money",
        required=False,
        padding="left_zero",
        justification="right",
        signed=False,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )
    record = ExportRecordDefinition(
        id="declaracion",
        record_type="declaracion",
        order=1,
        encoding=ExportEncoding.ASCII,
        line_ending="none",
        fields=(field,),
    )
    return ExportLayoutDefinition(id="layout", legal_refs=(_LEGAL_REF,), source_refs=(_SOURCE_REF,), records=(record,))


def _revision(*, grade: str, layouts: tuple[ExportLayoutDefinition, ...]) -> ModeloRevision:
    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
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
    findings = grade_findings(_revision(grade="filing", layouts=(_layout(),)), modelo_id="000")

    assert [(f.kind, f.prerequisite) for f in findings] == [("under_supported", "completeness_manifest")]


def test_applicability_grade_carrying_a_layout_is_under_declared() -> None:
    findings = grade_findings(_revision(grade="applicability", layouts=(_layout(),)), modelo_id="000")

    assert [(f.kind, f.prerequisite) for f in findings] == [("under_declared", "export_layout")]


def test_applicability_grade_carrying_nothing_is_clean() -> None:
    assert grade_findings(_revision(grade="applicability", layouts=()), modelo_id="000") == ()
