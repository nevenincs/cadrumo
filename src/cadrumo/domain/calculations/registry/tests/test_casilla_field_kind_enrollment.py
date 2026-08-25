"""Real-behavior CasillaFieldKind enrollment checks."""

from __future__ import annotations

import pytest

from .....core import BindingSourceKind, CasillaId, validated_casilla_id
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from ..._export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.schema import DataBindingDefinition, ExportFieldDefinition, ExportLayoutDefinition, ExportRecordDefinition
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from ..schema import PeriodSelector
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-35-2006:art-test"
_SOURCE_REF = "aeat-test-source-001"
_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_CASILLA_01")


def test_bundled_export_field_kinds_are_hydrated_enum_members() -> None:
    """Every committed export field reaches consumers as a CasillaFieldKind."""

    modelos, _catalogues = _committed_registry_tree()

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
    from ..withholding_bindings import _WithholdingSelector

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
        id="perceptor",
        record_type="perceptor",
        order=1,
        encoding=ExportEncoding.ASCII,
        line_ending="none",
        binding_record="perceptor",
        row_field_casilla_ids={"retencion_practicada": _CASILLA_01},
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
    derived_field = next(field for field in derived_record.fields if field.binding == "binding.rows")

    assert derived_field.kind is CasillaFieldKind.BINDING
    assert derived_field.id == template.id
    assert all(isinstance(field.kind, CasillaFieldKind) for field in derived_record.fields)


def test_m720_binding_fields_remain_visible_when_a_resolved_revision_is_derived_again() -> None:
    """Every casilla-keyed consumer may safely derive the real M720 layout first."""
    revision = bundled_authority().snapshot("720", filing_year=2025, period="0A").revision
    binding_fields = tuple(
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.BINDING
    )

    assert binding_fields
    assert len({field.id for field in binding_fields}) == len(binding_fields)
    assert derive_export_layouts_from_bindings(revision) == revision.export_layouts


def test_binding_derived_export_skips_source_mirror_when_row_field_is_hand_authored() -> None:
    """One official fixed-width field can represent multiple source-specific row bindings."""
    from ..withholding_bindings import _WithholdingSelector

    public_binding = DataBindingDefinition(
        id="binding.rows.public",
        source=BindingSourceKind.WITHHOLDING,
        selector=_WithholdingSelector.model_validate(
            {
                "fact": "row_field",
                "record": "perceptor",
                "row_field": "retencion_practicada",
                "grouping": "per_perceptor",
            }
        ),
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )
    mirror_binding = DataBindingDefinition(
        id="binding.rows.mirror",
        source=BindingSourceKind.WITHHOLDING,
        selector=_WithholdingSelector.model_validate(
            {
                "fact": "row_field",
                "record": "perceptor",
                "row_field": "retencion_practicada",
                "grouping": "per_perceptor",
            }
        ),
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )
    hand_authored_field = ExportFieldDefinition(
        id="ventas.importe",
        offset=1,
        length=10,
        kind=CasillaFieldKind.BINDING,
        binding=public_binding.id,
        data_type="money",
        required=False,
        padding="left_zero",
        justification="right",
        signed=False,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )
    record = ExportRecordDefinition(
        id="perceptor",
        record_type="perceptor",
        order=1,
        encoding=ExportEncoding.ASCII,
        line_ending="none",
        binding_record="perceptor",
        row_field_casilla_ids={"retencion_practicada": _CASILLA_01},
        fields=(hand_authored_field,),
    )
    revision = _minimal_revision(
        bindings=(public_binding, mirror_binding),
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

    assert tuple(field.binding for field in derived_record.fields if field.kind is CasillaFieldKind.BINDING) == (
        public_binding.id,
    )


def test_binding_derived_export_emits_one_field_for_source_mirror_template() -> None:
    """A casilla template row field becomes one binding export field, not one per source."""
    from ..withholding_bindings import _WithholdingSelector

    public_binding = DataBindingDefinition(
        id="binding.rows.public",
        source=BindingSourceKind.WITHHOLDING,
        selector=_WithholdingSelector.model_validate(
            {
                "fact": "row_field",
                "record": "perceptor",
                "row_field": "retencion_practicada",
                "grouping": "per_perceptor",
            }
        ),
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )
    mirror_binding = DataBindingDefinition(
        id="binding.rows.mirror",
        source=BindingSourceKind.WITHHOLDING,
        selector=_WithholdingSelector.model_validate(
            {
                "fact": "row_field",
                "record": "perceptor",
                "row_field": "retencion_practicada",
                "grouping": "per_perceptor",
            }
        ),
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
        id="perceptor",
        record_type="perceptor",
        order=1,
        encoding=ExportEncoding.ASCII,
        line_ending="none",
        binding_record="perceptor",
        row_field_casilla_ids={"retencion_practicada": _CASILLA_01},
        fields=(template,),
    )
    revision = _minimal_revision(
        bindings=(public_binding, mirror_binding),
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
    binding_fields = tuple(field for field in derived_record.fields if field.kind is CasillaFieldKind.BINDING)

    assert tuple(field.binding for field in binding_fields) == (public_binding.id,)
    assert binding_fields[0].offset == template.offset
    assert binding_fields[0].length == template.length


def _minimal_revision(
    *,
    bindings: tuple[DataBindingDefinition, ...],
    export_layouts: tuple[ExportLayoutDefinition, ...],
):
    from datetime import date

    from cadrumo.domain.calculations.registry.schema import ModeloRevision

    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        bindings=bindings,
        export_layouts=export_layouts,
    )
