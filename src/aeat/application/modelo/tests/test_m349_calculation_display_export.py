"""Modelo 349 calculation display and export parity for operator rows."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from ....application.filing import _filing_binding_values, render_layout
from ....core import Period
from ....core.resources import bundled_path
from ....domain.calculations.registry import (
    CasillaId,
    RegistrySnapshot,
    RegistrySnapshotRef,
    calculate_registry_snapshot,
    load_modelo_path,
    resolve_bound_inputs_by_casilla_id,
    validated_casilla_id,
)
from ....domain.filing import (
    ModeloCasillaProvenance,
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
)
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
    ModeloCode,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from ....domain.submission import ModeloDraftStatus
from ....entrypoints.cli import (
    calculation_revision_lines,
    calculation_revision_payload,
)
from .._calculation_actions import _detail_row_binding_values_for_calculation, _suppress_m349_row_field_template_outputs
from .._calculation_helpers import build_typed_observations
from .._revision_replay_inputs import _m349_detail_row_replay_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
_BUCKET_ID = "m349-display-export-parity"
_PROFILE_TAX_ID = "12345678Z"
_REVISION_ID = "2020-y-siguientes"
_DECL_NUMERO_OPERADORES: CasillaId = validated_casilla_id(
    "decl.numero-operadores",
    surface="test_m349_calculation_display_export",
)
_DECL_IMPORTE_OPERACIONES: CasillaId = validated_casilla_id(
    "decl.importe-operaciones",
    surface="test_m349_calculation_display_export",
)
_DECL_NUMERO_RECTIFICACIONES: CasillaId = validated_casilla_id(
    "decl.numero-rectificaciones",
    surface="test_m349_calculation_display_export",
)
_DECL_IMPORTE_RECTIFICACIONES: CasillaId = validated_casilla_id(
    "decl.importe-rectificaciones",
    surface="test_m349_calculation_display_export",
)


def _m349_snapshot(*, period: str) -> RegistrySnapshot:
    modelo = load_modelo_path(bundled_path("registry", "aeat", "modelos", "349"))
    revision = modelo.revisions[_REVISION_ID]
    filing_period = Period.from_year_and_code(2026, period)
    return RegistrySnapshot(
        modelo=modelo,
        revision=revision,
        filing_period=filing_period,
        filing_year=2026,
        period=period,
        legal={},
        sources={},
        extraction_profiles={profile.id: profile for profile in revision.extraction_profiles},
        live_cross_references={item.id: item for item in revision.live_cross_references},
        workbook_parity_refs={item.id: item for item in revision.workbook_parity_refs},
        verification_expectations={item.id: item for item in revision.verification_expectations},
        application_links={item.id: item for item in revision.application_links},
        deadline_windows={item.id: item for item in revision.deadline_windows},
        filing_schedules={item.id: item for item in revision.filing_schedules},
        support_removal_decisions={item.id: item for item in revision.support_removal_decisions},
        constructs={item.id: item for item in revision.constructs},
        dependency_classifications={item.id: item for item in revision.dependency_classifications},
    )


def _work_unit(*, period: str, snapshot: RegistrySnapshot) -> WorkUnit:
    filing_period = Period.from_year_and_code(2026, period)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=filing_period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("349"),
        filing_year=2026,
        period=filing_period,
        revision_id=snapshot.revision.id,
        name=f"349-2026-{period}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _calculated_revision(
    *,
    period: str,
    country: str,
    vat_id: str,
    name: str,
    clave: str,
    amount: Decimal,
) -> tuple[RegistrySnapshot, WorkUnit, CalculationRevision]:
    snapshot = _m349_snapshot(period=period)
    work_unit = _work_unit(period=period, snapshot=snapshot)
    row = Modelo349OperadorRow.model_validate(
        {
            "codigo_pais": country,
            "nif_comunitario": vat_id,
            "razon_social": name,
            "clave_operacion": clave,
            "importe": amount,
        }
    )
    binding_values = {
        "iva-349-declarante-numero-operadores": Decimal("1"),
        "iva-349-declarante-importe-operaciones": amount,
        "iva-349-declarante-numero-rectificaciones": Decimal("0"),
        "iva-349-declarante-importe-rectificaciones": Decimal("0"),
    }
    inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": work_unit.period.end_date},
        binding_values=binding_values,
    )
    raw_casilla_values = dict(engine_result.values)
    raw_observations = build_typed_observations(engine_result=engine_result, snapshot=snapshot)

    assert raw_casilla_values["op.codigo-pais"] == Decimal("0")
    assert raw_casilla_values["op.nif-comunitario"] == Decimal("0")
    assert raw_casilla_values["op.clave-operacion"] == Decimal("0")
    assert raw_casilla_values["op.base-imponible"] == Decimal("0")

    input_values = {casilla_id: str(value) for casilla_id, value in inputs.items()}
    binding_overrides = {binding_id: str(value) for binding_id, value in binding_values.items()}
    detail_rows = (row,)
    legacy_revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id=input_values,
            binding_overrides=binding_overrides,
            casilla_values=raw_casilla_values,
            detail_rows=detail_rows,
        ),
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values,
        binding_overrides=binding_overrides,
        casilla_values=raw_casilla_values,
        observations=raw_observations,
        detail_rows=detail_rows,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    calc_lines: Any = calculation_revision_lines
    calc_payload: Any = calculation_revision_payload
    legacy_rendered_revision = "\n".join(calc_lines(legacy_revision))
    legacy_payload = calc_payload(legacy_revision)
    assert "casilla\top." not in legacy_rendered_revision
    assert "casilla\trect." not in legacy_rendered_revision
    assert not any(casilla_id.startswith("op.") for casilla_id in legacy_payload.casilla_values)
    assert not any(casilla_id.startswith("rect.") for casilla_id in legacy_payload.casilla_values)

    casilla_values, observations = _suppress_m349_row_field_template_outputs(
        work_unit=work_unit,
        revision=snapshot.revision,
        casilla_values=raw_casilla_values,
        observations=raw_observations,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=input_values,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        detail_rows=detail_rows,
    )
    return (
        snapshot,
        work_unit,
        CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=work_unit.work_unit_id,
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id=input_values,
            binding_overrides=binding_overrides,
            casilla_values=casilla_values,
            observations=observations,
            detail_rows=detail_rows,
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


def _approved_draft(
    *,
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    revision: CalculationRevision,
) -> ModeloDraft:
    values = tuple(
        ModeloValue(
            casilla_id=casilla_id,
            value=value,
            kind=ModeloValueKind.INHERITED,
            source="registry calculation",
        )
        for casilla_id, value in sorted(revision.casilla_values.items())
    )
    replay_inputs = _m349_detail_row_replay_inputs(revision=revision, work_unit=work_unit)
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    binding_values = tuple(_filing_binding_values(replay_inputs, bindings_by_id))
    casilla_provenance = tuple(
        ModeloCasillaProvenance(
            casilla_id=casilla.id,
            formula_id=casilla.formula,
            legal_refs=tuple(casilla.legal_refs),
            source_refs=tuple(casilla.source_refs),
        )
        for casilla in sorted(snapshot.revision.casillas, key=lambda item: item.id)
    )
    schema_version = f"registry:{snapshot.modelo.id}:{snapshot.revision.id}"
    snapshot_ref = RegistrySnapshotRef(
        modelo="349",
        revision_id=snapshot.revision.id,
        modelo_year=2026,
        period=work_unit.period.registry_token,
    )
    draft_id = compute_modelo_draft_id(
        modelo="349",
        period=work_unit.period,
        profile_tax_id=_PROFILE_TAX_ID,
        snapshot_ref=snapshot_ref,
        values=values,
        binding_values=binding_values,
    )
    return ModeloDraft(
        draft_id=draft_id,
        modelo="349",
        period=work_unit.period,
        profile_tax_id=_PROFILE_TAX_ID,
        subject_tax_id=_PROFILE_TAX_ID,
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.APROBADO,
        values=values,
        binding_values=binding_values,
        casilla_provenance=casilla_provenance,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        schema_version=schema_version,
        approved_at=_CLOCK,
        approved_by="operator",
    )


@pytest.mark.parametrize(
    ("period", "country", "vat_id", "name", "clave", "amount", "export_amount"),
    (
        ("2T", "DE", "DE123456789", "DE Auto GmbH", "E", Decimal("1500.00"), "0000000150000"),
        ("3T", "FR", "FR12345678901", "Equipement Garage SARL", "A", Decimal("800.00"), "0000000080000"),
    ),
)
def test_m349_calculation_revision_display_and_export_agree_for_operator_row(
    period: str,
    country: str,
    vat_id: str,
    name: str,
    clave: str,
    amount: Decimal,
    export_amount: str,
) -> None:
    snapshot, work_unit, revision = _calculated_revision(
        period=period,
        country=country,
        vat_id=vat_id,
        name=name,
        clave=clave,
        amount=amount,
    )

    assert revision.casilla_values == {
        _DECL_NUMERO_OPERADORES: Decimal("1"),
        _DECL_IMPORTE_OPERACIONES: amount,
        _DECL_NUMERO_RECTIFICACIONES: Decimal("0"),
        _DECL_IMPORTE_RECTIFICACIONES: Decimal("0"),
    }
    calc_lines_inner: Any = calculation_revision_lines
    rendered_revision = "\n".join(calc_lines_inner(revision))
    assert "casilla\top." not in rendered_revision
    assert "casilla\trect." not in rendered_revision
    assert f"detail_row\t1\toperador\tcodigo_pais={country}" in rendered_revision
    assert f"nif_comunitario={vat_id}" in rendered_revision
    assert f"razon_social={name}" in rendered_revision
    assert f"clave_operacion={clave}" in rendered_revision
    assert f"importe={amount}" in rendered_revision

    draft = _approved_draft(snapshot=snapshot, work_unit=work_unit, revision=revision)
    payload = render_layout(snapshot.revision.export_layouts[0], draft=draft, headers={})
    records = [payload[index : index + 500].decode("latin-1") for index in range(0, len(payload), 500)]
    operator_records = [record for record in records if record.startswith("2349")]

    assert len(operator_records) == 1
    record = operator_records[0]
    assert record[75:92].rstrip() == vat_id
    assert record[92:132].strip() == name
    assert record[132] == clave
    assert record[133:146] == export_amount


def test_m349_rectification_detail_row_feeds_summary_display_and_export() -> None:
    snapshot = _m349_snapshot(period="2T")
    work_unit = _work_unit(period="2T", snapshot=snapshot)
    row = Modelo349RectificacionRow(
        codigo_pais="DE",
        nif_comunitario="DE123456789",
        razon_social="DE Auto GmbH",
        clave_operacion="E",
        ejercicio="2025",
        periodo="1T",
        base_rectificada=Decimal("1100.00"),
        base_anterior=Decimal("1000.00"),
    )
    detail_rows = (row,)
    binding_values = _detail_row_binding_values_for_calculation(
        work_unit=work_unit,
        detail_rows=detail_rows,
    )

    assert binding_values == {
        "iva-349-declarante-numero-operadores": Decimal("0"),
        "iva-349-declarante-importe-operaciones": Decimal("0"),
        "iva-349-declarante-numero-rectificaciones": Decimal("1"),
        "iva-349-declarante-importe-rectificaciones": Decimal("100.00"),
    }

    inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": work_unit.period.end_date},
        binding_values=binding_values,
    )
    raw_casilla_values = dict(engine_result.values)
    raw_observations = build_typed_observations(engine_result=engine_result, snapshot=snapshot)
    casilla_values, observations = _suppress_m349_row_field_template_outputs(
        work_unit=work_unit,
        revision=snapshot.revision,
        casilla_values=raw_casilla_values,
        observations=raw_observations,
    )
    input_values = {casilla_id: str(value) for casilla_id, value in inputs.items()}
    binding_overrides = {binding_id: str(value) for binding_id, value in binding_values.items()}
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id=input_values,
            binding_overrides=binding_overrides,
            casilla_values=casilla_values,
            detail_rows=detail_rows,
        ),
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        observations=observations,
        detail_rows=detail_rows,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )

    assert revision.casilla_values == {
        _DECL_NUMERO_OPERADORES: Decimal("0"),
        _DECL_IMPORTE_OPERACIONES: Decimal("0"),
        _DECL_NUMERO_RECTIFICACIONES: Decimal("1"),
        _DECL_IMPORTE_RECTIFICACIONES: Decimal("100.00"),
    }
    calc_lines_rect: Any = calculation_revision_lines
    rendered_revision = "\n".join(calc_lines_rect(revision))
    assert "casilla\trect." not in rendered_revision
    assert "detail_row\t1\trectificacion\tcodigo_pais=DE" in rendered_revision
    assert "ejercicio=2025" in rendered_revision
    assert "periodo=1T" in rendered_revision
    assert "base_rectificada=1100.00" in rendered_revision
    assert "base_anterior=1000.00" in rendered_revision

    draft = _approved_draft(snapshot=snapshot, work_unit=work_unit, revision=revision)
    payload = render_layout(snapshot.revision.export_layouts[0], draft=draft, headers={})
    records = [payload[index : index + 500].decode("latin-1") for index in range(0, len(payload), 500)]
    rectification_records = [record for record in records if record.startswith("2349") and record[146:178].strip()]

    assert len(rectification_records) == 1
    record = rectification_records[0]
    assert record[75:92].rstrip() == "DE123456789"
    assert record[92:132].strip() == "DE Auto GmbH"
    assert record[132] == "E"
    assert record[133:146].strip() == ""
    assert record[146:150] == "2025"
    assert record[150:152] == "1T"
    assert record[152:165] == "0000000110000"
    assert record[165:178] == "0000000100000"
