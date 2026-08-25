"""Exact-address preflight proofs for filing projections."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core import (
    M303DifferentiatedDeductionProjectionField,
    M303DifferentiatedDeductionProjectionRef,
    M303Exonerado390ActivityField,
    M303Exonerado390ActivityProjectionRef,
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
    Modelo,
    ResultDisposition,
)
from cadrumo.domain.calculations.registry.schema import CasillaFieldKind, ExportFieldDefinition, ExportLayoutDefinition, ExportRecordDefinition
from cadrumo.domain.calculations.registry.authority import bundled_authority
from ....domain.filing import FilingExportValidationError
from .. import build_filing_producer_snapshot
from .._export import _preflight_projection_plan
from .._projection import (
    FilingProjectionPlan,
    FilingProjectionValue,
    FilingRecordRenderContext,
    _project_record,
    _require_regimen_snapshot_matches_registry,
    build_m303_filing_projection_plan,
)
from .test_producer_snapshot import _elections, _m303_filing_facts, _m303_profile, _presenter, _taxpayer_identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _projection_authority() -> tuple[FilingRecordRenderContext, M303ProrrataActivityProjectionRef]:
    reference = M303ProrrataActivityProjectionRef(
        projection_kind="m303_prorrata_activity",
        slot=1,
        field=M303ProrrataActivityProjectionField.CNAE,
        casilla_id="500",
    )
    field = ExportFieldDefinition(
        id="projection-field",
        offset=1,
        length=4,
        kind=CasillaFieldKind.PROJECTION,
        projection_ref=reference,
        data_type="text",
        required=True,
        padding="right_space",
        justification="left",
        signed=False,
        legal_refs=("ley-27-2014:art-40",),
        source_refs=("aeat-dr-200-2025",),
    )
    record = ExportRecordDefinition(
        id="projection-record",
        record_type="detalle",
        order=1,
        encoding="latin-1",
        line_ending="none",
        repeat="projection_rows",
        fields=(field,),
    )
    layout = ExportLayoutDefinition(
        id="projection-layout",
        format="fixed_width",
        records=(record,),
        legal_refs=("ley-27-2014:art-40",),
        source_refs=("aeat-dr-200-2025",),
    )
    base = bundled_authority().snapshot("200", filing_year=2025, period="0A")
    snapshot = base.model_copy(update={"revision": base.revision.model_copy(update={"export_layouts": (layout,)})})
    return FilingRecordRenderContext(
        registry_snapshot=snapshot,
        layout=layout,
        record=record,
        occurrence=1,
    ), reference


def test_projection_value_refuses_raw_reference_and_nonpositive_occurrence() -> None:
    context, reference = _projection_authority()
    payload = {
        "projection_ref": reference.model_dump(mode="python"),
        "record_id": context.record.id,
        "occurrence": 1,
        "value": "722",
    }
    with pytest.raises(ValidationError, match="actual typed projection_ref"):
        FilingProjectionValue.model_validate(payload)
    with pytest.raises(ValidationError, match="greater than 0"):
        FilingProjectionValue(projection_ref=reference, record_id=context.record.id, occurrence=0, value="722")


def test_projection_preflight_accepts_only_the_exact_address_bijection() -> None:
    context, reference = _projection_authority()
    value = FilingProjectionValue(
        projection_ref=reference,
        record_id=context.record.id,
        occurrence=1,
        value="722",
    )
    assert _preflight_projection_plan(FilingProjectionPlan(contexts=(context,), values=(value,))) == {
        (context.record.id, 1, reference): "722",
    }

    for invalid_values in (
        (),
        (value, value),
        (
            value,
            value.model_copy(
                update={
                    "projection_ref": M303DifferentiatedDeductionProjectionRef(
                        projection_kind="m303_differentiated_deduction",
                        slot=1,
                        field=M303DifferentiatedDeductionProjectionField.TOTAL,
                        casilla_id="599",
                    ),
                },
            ),
        ),
        (value.model_copy(update={"record_id": "other-record"}),),
        (value.model_copy(update={"occurrence": 2}),),
    ):
        with pytest.raises(FilingExportValidationError):
            _preflight_projection_plan(FilingProjectionPlan(contexts=(context,), values=invalid_values))

    with pytest.raises(FilingExportValidationError, match="duplicate record occurrences"):
        _preflight_projection_plan(FilingProjectionPlan(contexts=(context, context), values=(value,)))


def test_render_context_and_m303_builder_refuse_nonowned_or_cross_period_authority() -> None:
    context, _reference = _projection_authority()
    unrelated_snapshot = bundled_authority().snapshot("200", filing_year=2025, period="0A")
    with pytest.raises(ValidationError, match="layout is not owned"):
        FilingRecordRenderContext(
            registry_snapshot=unrelated_snapshot,
            layout=context.layout,
            record=context.record,
            occurrence=1,
        )

    producer = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=_m303_filing_facts(period_code="1T"),
    )
    snapshot_2026 = bundled_authority().snapshot("303", filing_year=2026, period="1T")
    snapshot_2025 = bundled_authority().snapshot("303", filing_year=2025, period="4T")
    with pytest.raises(FilingExportValidationError, match="filing period"):
        build_m303_filing_projection_plan(
            registry_snapshot=snapshot_2025,
            layout=context.layout,
            producer_snapshot=producer,
        )
    with pytest.raises(FilingExportValidationError, match="layout is not owned"):
        build_m303_filing_projection_plan(
            registry_snapshot=snapshot_2026,
            layout=context.layout,
            producer_snapshot=producer,
        )
    mixed_ref = M303DifferentiatedDeductionProjectionRef(
        projection_kind="m303_differentiated_deduction",
        slot=1,
        field=M303DifferentiatedDeductionProjectionField.TOTAL,
        casilla_id="599",
    )
    admitted_ref = context.record.fields[0].projection_ref
    assert admitted_ref is not None
    unsupported_third_family = M303Exonerado390ActivityProjectionRef(
        projection_kind="m303_exonerado_390_activity",
        slot=1,
        field=M303Exonerado390ActivityField.ACTIVITY_CODE,
    )
    with pytest.raises(FilingExportValidationError, match="mixes or uses an unsupported"):
        _project_record(
            registry_snapshot=snapshot_2026,
            layout=context.layout,
            record=context.record,
            refs=(admitted_ref, mixed_ref, unsupported_third_family),
            producer_snapshot=producer,
        )


@pytest.mark.parametrize(
    "orden_update",
    (
        {"ejercicio": 2025},
        {"registry_revision_id": "wrong-revision"},
        {"source_ref": "wrong-source"},
    ),
)
def test_m303_projection_refuses_wrong_annual_orden_authority(orden_update: dict[str, object]) -> None:
    producer = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=_m303_filing_facts(),
    )
    facts = producer.m303_filing_facts
    assert facts is not None
    evidence = facts.regimen_simplificado
    regimen_snapshot = evidence.regimen_snapshot
    wrong_regimen_snapshot = regimen_snapshot.model_copy(
        update={"orden": regimen_snapshot.orden.model_copy(update=orden_update)},
    )
    wrong_evidence = evidence.model_copy(update={"regimen_snapshot": wrong_regimen_snapshot})
    wrong_facts = facts.model_copy(update={"regimen_simplificado": wrong_evidence})
    wrong_producer = producer.model_copy(update={"m303_filing_facts": wrong_facts})
    snapshot = bundled_authority().snapshot("303", filing_year=2026, period="1T")

    with pytest.raises(FilingExportValidationError, match="annual Orden"):
        _require_regimen_snapshot_matches_registry(snapshot, wrong_producer)
