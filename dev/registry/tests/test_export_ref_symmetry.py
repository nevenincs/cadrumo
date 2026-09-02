"""The export-ref symmetry guard reports a broken edge and nothing else.

Detector teeth come from constructed revisions: an unsatisfied ``export_refs``
claim is reported with its coordinates, a satisfied one is not, and a casilla
that makes no claim is never reported. The bundled registry is then held to
the property the guard protects: with all three linkage paths resolved, the
edge is symmetric, so the residue is empty. That is a property of the edge,
not a tally, and it is exactly what a future regression would break.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.schema import CasillaDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from ..analysis.export_ref_symmetry import screen_authority, unsatisfied_export_refs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-35-2006:art-test"
_SOURCE_REF = "aeat-test-source-001"
_CASILLA_01 = validated_casilla_id("01", surface="_CASILLA_01")


def _casilla(*, export_refs: tuple[str, ...]) -> CasillaDefinition:
    return CasillaDefinition(
        id=_CASILLA_01,
        number="01",
        localization_keys=("test.schema.casilla.label",),
        section=("totales",),
        input_kind=InputKind.MANUAL,
        export_refs=export_refs,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


def _layout_carrying_casilla_01() -> ExportLayoutDefinition:
    field = ExportFieldDefinition(
        id="importe",
        offset=1,
        length=10,
        kind=CasillaFieldKind.CASILLA,
        casilla_id=_CASILLA_01,
        data_type=CasillaDataType.MONEY,
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
    return ExportLayoutDefinition(
        id="layout",
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        records=(record,),
    )


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


def test_satisfied_export_ref_is_not_reported() -> None:
    revision = _revision(
        casillas=(_casilla(export_refs=("layout.declaracion.importe",)),),
        layouts=(_layout_carrying_casilla_01(),),
    )

    assert unsatisfied_export_refs(revision, modelo_id="000") == ()


def test_unsatisfied_export_ref_is_reported_with_its_coordinates() -> None:
    revision = _revision(
        casillas=(_casilla(export_refs=("layout.declaracion.importe",)),),
        layouts=(),
    )

    (finding,) = unsatisfied_export_refs(revision, modelo_id="000")

    assert (finding.modelo, finding.revision, finding.casilla_id) == ("000", "test-revision", _CASILLA_01)
    assert finding.export_refs == ("layout.declaracion.importe",)


def test_casilla_without_export_refs_makes_no_claim() -> None:
    revision = _revision(casillas=(_casilla(export_refs=()),), layouts=())

    assert unsatisfied_export_refs(revision, modelo_id="000") == ()


def test_bundled_registry_export_edge_is_symmetric() -> None:
    """Every ``export_refs`` claim in the shipped registry is carried by the resolved surface."""
    authority = bundled_authority()

    findings = screen_authority(authority, tuple(sorted(registry_modelo_codes())))

    assert findings == (), "\n".join(
        f"{f.modelo}/{f.revision} casilla {f.casilla_id} claims {','.join(f.export_refs)} "
        "but the resolved surface does not carry it"
        for f in findings
    )
