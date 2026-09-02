"""The provenance screen reports a child citation outside its manifest, and reads resolved export fields.

Detector teeth on constructed revisions: a casilla citing only manifest refs is
clean; a casilla citing an extra legal ref is reported as a ``legal`` finding
naming exactly that ref; an export field citing an extra source ref is
reported as an ``export_field`` finding through the resolved surface, with the
field's resolved coordinates as its id.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.schema import CasillaDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from ..analysis.provenance_consistency import provenance_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-35-2006:art-test"
_EXTRA_LEGAL_REF = "ley-37-1992:art-extra"
_SOURCE_REF = "aeat-test-source-001"
_EXTRA_SOURCE_REF = "aeat-test-source-002"
_CASILLA_01 = validated_casilla_id("01", surface="_CASILLA_01")


def _casilla(*, legal_refs: tuple[str, ...]) -> CasillaDefinition:
    return CasillaDefinition(
        id=_CASILLA_01,
        number="01",
        localization_keys=("test.schema.casilla.label",),
        section=("totales",),
        input_kind=InputKind.MANUAL,
        legal_refs=legal_refs,
        source_refs=(_SOURCE_REF,),
    )


def _layout(*, field_source_refs: tuple[str, ...]) -> ExportLayoutDefinition:
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
        source_refs=field_source_refs,
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


def _revision(
    *, casillas: tuple[CasillaDefinition, ...], layouts: tuple[ExportLayoutDefinition, ...]
) -> ModeloRevision:
    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        casillas=casillas,
        export_layouts=layouts,
    )


def test_child_inside_manifest_is_clean() -> None:
    revision = _revision(
        casillas=(_casilla(legal_refs=(_LEGAL_REF,)),), layouts=(_layout(field_source_refs=(_SOURCE_REF,)),)
    )

    assert provenance_findings(revision, modelo_id="000") == ()


def test_casilla_citing_outside_legal_ref_is_reported_with_the_ref() -> None:
    revision = _revision(casillas=(_casilla(legal_refs=(_LEGAL_REF, _EXTRA_LEGAL_REF)),), layouts=())

    (finding,) = provenance_findings(revision, modelo_id="000")

    assert (finding.child_kind, finding.child_id, finding.ref_kind) == ("casilla", str(_CASILLA_01), "legal")
    assert finding.outside == (_EXTRA_LEGAL_REF,)


def test_resolved_export_field_citing_outside_source_is_reported() -> None:
    revision = _revision(
        casillas=(_casilla(legal_refs=(_LEGAL_REF,)),),
        layouts=(_layout(field_source_refs=(_SOURCE_REF, _EXTRA_SOURCE_REF)),),
    )

    (finding,) = provenance_findings(revision, modelo_id="000")

    assert (finding.child_kind, finding.child_id, finding.ref_kind) == (
        "export_field",
        "layout.declaracion.importe",
        "source",
    )
    assert finding.outside == (_EXTRA_SOURCE_REF,)
