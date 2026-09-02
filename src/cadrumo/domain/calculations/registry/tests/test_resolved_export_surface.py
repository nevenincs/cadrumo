"""The resolved-surface accessor needs all three linkage paths; dropping any one loses a casilla.

The fixture puts one casilla behind each path and nothing else: ``01`` behind
a plain casilla-kind field, ``500`` behind a projection field, ``02`` behind a
binding-record row mapping whose template field derivation rewrites into a
binding-kind field. Each partial walk below is a real reading a consumer has
shipped in this campaign, and each misses exactly the casilla its dropped
path carries. The accessor must return all three.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.filing_projection_ref import (
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
)
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.withholding_bindings import _WithholdingSelector

from ..export import resolved_export_casillas, resolved_export_endpoints

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-35-2006:art-test"
_SOURCE_REF = "aeat-test-source-001"
_FIELD_CASILLA = validated_casilla_id("01", surface="field path")
_ROW_CASILLA = validated_casilla_id("02", surface="row-field path")
_PROJECTION_CASILLA = validated_casilla_id("500", surface="projection path")


def _casilla_field(field_id: str, casilla_id: CasillaId, *, offset: int) -> ExportFieldDefinition:
    return ExportFieldDefinition(
        id=field_id,
        offset=offset,
        length=10,
        kind=CasillaFieldKind.CASILLA,
        casilla_id=casilla_id,
        data_type="money",
        required=False,
        padding="left_zero",
        justification="right",
        signed=False,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


def _projection_field() -> ExportFieldDefinition:
    return ExportFieldDefinition(
        id="cnae.projection",
        offset=21,
        length=4,
        kind=CasillaFieldKind.PROJECTION,
        projection_ref=M303ProrrataActivityProjectionRef(
            projection_kind="m303_prorrata_activity",
            slot=1,
            field=M303ProrrataActivityProjectionField.CNAE,
            casilla_id=_PROJECTION_CASILLA,
        ),
        data_type="text",
        required=False,
        padding="right_space",
        justification="left",
        signed=False,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


def _three_path_revision() -> ModeloRevision:
    selector = _WithholdingSelector.model_validate(
        {
            "fact": "row_field",
            "record": "perceptor",
            "row_field": "retencion_practicada",
            "grouping": "per_perceptor",
        }
    )
    binding = DataBindingDefinition(
        id="binding.rows",
        source=BindingSourceKind.WITHHOLDING,
        selector=selector,
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )
    inline_record = ExportRecordDefinition(
        id="declaracion",
        record_type="declaracion",
        order=1,
        encoding=ExportEncoding.ASCII,
        line_ending="none",
        fields=(_casilla_field("importe", _FIELD_CASILLA, offset=1), _projection_field()),
    )
    row_record = ExportRecordDefinition(
        id="perceptor",
        record_type="perceptor",
        order=2,
        encoding=ExportEncoding.ASCII,
        line_ending="none",
        binding_record="perceptor",
        row_field_casilla_ids={"retencion_practicada": _ROW_CASILLA},
        fields=(_casilla_field("retencion.template", _ROW_CASILLA, offset=1),),
    )
    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        bindings=(binding,),
        export_layouts=(
            ExportLayoutDefinition(
                id="layout",
                legal_refs=(_LEGAL_REF,),
                source_refs=(_SOURCE_REF,),
                records=(inline_record, row_record),
            ),
        ),
    )


def test_accessor_returns_all_three_paths() -> None:
    revision = _three_path_revision()

    assert resolved_export_casillas(revision) == {_FIELD_CASILLA, _PROJECTION_CASILLA, _ROW_CASILLA}
    assert {(e.casilla_id, e.path) for e in resolved_export_endpoints(revision)} == {
        (_FIELD_CASILLA, "field"),
        (_PROJECTION_CASILLA, "projection"),
        (_ROW_CASILLA, "row_field"),
    }


def test_dropping_the_projection_fallback_loses_the_projection_casilla() -> None:
    """A walk reading ``casilla_id`` only (the second wrong figure) misses ``500``."""
    revision = _three_path_revision()
    casilla_id_only = {
        field.casilla_id
        for layout in derive_export_layouts_from_bindings(revision)
        for record in layout.records
        for field in record.fields
        if field.casilla_id is not None
    } | {
        casilla
        for layout in derive_export_layouts_from_bindings(revision)
        for record in layout.records
        for casilla in record.row_field_casilla_ids.values()
    }

    assert resolved_export_casillas(revision) - casilla_id_only == {_PROJECTION_CASILLA}


def test_dropping_the_row_mapping_loses_the_row_casilla() -> None:
    """A field-only walk (the third wrong figure) misses ``02`` on the resolved surface."""
    revision = _three_path_revision()
    fields_only = {
        field.endpoint_casilla_id
        for layout in derive_export_layouts_from_bindings(revision)
        for record in layout.records
        for field in record.fields
        if field.endpoint_casilla_id is not None
    }

    assert resolved_export_casillas(revision) - fields_only == {_ROW_CASILLA}


def test_reading_the_authored_surface_misclassifies_the_row_casilla() -> None:
    """Skipping derivation (the first wrong figure) reads ``02`` as a field-addressed casilla.

    On the authored layout the template field still names ``02``; after
    derivation that field names the binding and ``02`` is reachable only
    through the row mapping. The accessor must report the resolved reading.
    """
    revision = _three_path_revision()
    authored_field_casillas = {
        field.casilla_id
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None
    }
    resolved_paths = {e.casilla_id: e.path for e in resolved_export_endpoints(revision)}

    assert _ROW_CASILLA in authored_field_casillas
    assert resolved_paths[_ROW_CASILLA] == "row_field"
    assert all(e.field is None for e in resolved_export_endpoints(revision) if e.path == "row_field")
