"""Real-behavior CasillaFieldKind enrollment checks."""

from __future__ import annotations

import pytest

from .....core import BindingSourceKind
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.resources import bundled_path
from ..._export_field_kind import CasillaFieldKind
from .. import (
    CasillaId,
    DataBindingDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    derive_export_layouts_from_bindings,
    load_registry_tree,
    validated_casilla_id,
)
from .._schema import PeriodSelector

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "lirpf:art-test"
_SOURCE_REF = "aeat-test-source-001"
_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_CASILLA_01")


def test_bundled_export_field_kinds_are_hydrated_enum_members() -> None:
    """Every committed export field reaches consumers as a CasillaFieldKind."""

    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    checked = 0
    offenders: list[str] = []
    for modelo in modelos:
        for revision_id, revision in modelo.revisions.items():
            for layout in revision.export_layouts:
                for record in layout.records:
                    for field in record.fields:
                        checked += 1
                        if not isinstance(field.kind, CasillaFieldKind):
                            offenders.append(
                                f"modelo {modelo.id} revision {revision_id} "
                                f"field {layout.id}.{record.id}.{field.id} kind={field.kind!r}",
                            )

    assert checked, "bundled registry exposes no export fields"
    assert not offenders, "export field kinds were not hydrated as CasillaFieldKind:\n  " + "\n  ".join(offenders)


def test_binding_derived_export_fields_preserve_enum_kind() -> None:
    """The binding-derived export path emits CasillaFieldKind members."""

    binding = DataBindingDefinition(
        id="binding.rows",
        source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        selector={"record": "ventas", "row_field": "importe"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )
    template = ExportFieldDefinition(
        id="importe.template",
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
        id="ventas",
        record_type="ventas",
        order=1,
        encoding="utf-8",
        line_ending="none",
        binding_record="ventas",
        row_field_casilla_ids={"importe": _CASILLA_01},
        fields=(template,),
    )
    revision = _minimal_revision(
        bindings=(binding,),
        export_layouts=(
            ExportLayoutDefinition(
                id="layout",
                legal_refs=(_LEGAL_REF,),
                source_refs=(_SOURCE_REF,),
                records=(record,),
            ),
        ),
    )

    (layout,) = derive_export_layouts_from_bindings(revision)
    (derived_record,) = layout.records
    derived_field = next(field for field in derived_record.fields if field.id == "ventas.binding.rows")

    assert derived_field.kind is CasillaFieldKind.BINDING
    assert all(isinstance(field.kind, CasillaFieldKind) for field in derived_record.fields)


def _minimal_revision(
    *,
    bindings: tuple[DataBindingDefinition, ...],
    export_layouts: tuple[ExportLayoutDefinition, ...],
):
    from datetime import date

    from .. import ModeloRevision

    return ModeloRevision(
        id="test-revision",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        bindings=bindings,
        export_layouts=export_layouts,
    )
