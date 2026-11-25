"""A one-field fixed-width export layout whose single field carries casilla 01."""

from __future__ import annotations

from datetime import date

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

LEGAL_REF = "ley-35-2006:art-test"
SOURCE_REF = "aeat-test-source-001"
CASILLA_01 = validated_casilla_id("01", surface="CASILLA_01")


def single_casilla_export_layout(*, field_source_refs: tuple[str, ...] = (SOURCE_REF,)) -> ExportLayoutDefinition:
    field = ExportFieldDefinition(
        id="importe",
        offset=1,
        length=10,
        kind=CasillaFieldKind.CASILLA,
        casilla_id=CASILLA_01,
        data_type=CasillaDataType.MONEY,
        required=False,
        padding="left_zero",
        justification="right",
        signed=False,
        legal_refs=(LEGAL_REF,),
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
    return ExportLayoutDefinition(id="layout", legal_refs=(LEGAL_REF,), source_refs=(SOURCE_REF,), records=(record,))


def revision_with(
    *, casillas: tuple[CasillaDefinition, ...], layouts: tuple[ExportLayoutDefinition, ...]
) -> ModeloRevision:
    """A first-quarter revision of the support horizon citing the shared legal and source references."""
    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(filing_year_envelope().horizon, 1, 1),
        period_selector=PeriodSelector(years=(filing_year_envelope().horizon,), periods=("1T",)),
        legal_refs=(LEGAL_REF,),
        source_refs=(SOURCE_REF,),
        casillas=casillas,
        export_layouts=layouts,
    )
